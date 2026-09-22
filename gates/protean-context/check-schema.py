#!/usr/bin/env python3
"""check-schema.py - gate 2 of build/verify-all.py.

Proves:

  * every JSON file shipped in this tree parses;
  * each of the four schema documents carries its two identity fields
    (`schema`, `schemaVersion`) and documents the same pair for the files it
    describes;
  * the shipped templates validate against their schema documents;
  * a real `init` + `ingest` run against the synthetic fixtures produces
    records that validate as arif-record-v1, with `content.ref` pointers that
    resolve inside `content/` and checksums that match the stored bytes.

The synthetic fixtures under tests/fixtures/ are the only input: real corpus is
never read (architecture decision D4 of the protean-context lock (2026-09-22)).

Usage: python3 gates/protean-context/check-schema.py [repo-root]
Exit: 0 pass; 1 violation; 2 missing source data.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile

GATE = "check-schema.py"
DOCUMENT_SCHEMAS = ("eldunarya-v1", "arif-store-v1", "arif-record-v1")
TREE_SCHEMAS = ("eldunari-v1",)
SKIP_DIRS = (".git", "__pycache__", ".protean-backup")
FIXTURE_ADAPTER = "tests/fixtures/adapter_synthetic.py"
FIXTURE_SOURCE = "tests/fixtures/source"
RECORD_SCHEMA = "arif-record-v1"


def find_json(root):
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(".json"):
                found.append(os.path.relpath(os.path.join(base, name), root))
    return sorted(found)


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    scripts = os.path.join(root, "scripts", "protean-context")
    adapter = os.path.join(root, FIXTURE_ADAPTER)
    source = os.path.join(root, FIXTURE_SOURCE)
    bootstrap = os.path.join(scripts, "bootstrap.py")
    for path in (bootstrap, adapter, source):
        if not os.path.exists(path):
            sys.stderr.write("MISSING: %s\n" % os.path.relpath(path, root))
            return 2
    sys.path.insert(0, scripts)
    import pc_schema
    import pc_paths

    problems = []
    scanned = 0
    for rel in find_json(root):
        path = os.path.join(root, rel)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                json.load(handle)
        except ValueError as exc:
            problems.append("%s: does not parse (%s)" % (rel, exc))
        else:
            scanned += 1

    schema_dir = os.path.join(root, "templates", "protean-context", "schema")
    schema_names = []
    for name in pc_paths.SCHEMA_DOCUMENTS.values():
        path = os.path.join(schema_dir, name)
        if not os.path.isfile(path):
            sys.stderr.write("MISSING: %s\n" % os.path.relpath(path, root))
            return 2
        document = pc_schema.load_schema_document(path)
        schema_names.append(document["schema"])
        if not isinstance(document.get("title"), str) or not document["title"]:
            problems.append("%s: has no title" % name)
        if not isinstance(document.get("description"), str):
            problems.append("%s: has no description" % name)
        properties = document.get("properties") or {}
        required = document.get("required") or []
        if document["schema"] in DOCUMENT_SCHEMAS:
            for field in ("schema", "schemaVersion"):
                if field not in properties or field not in required:
                    problems.append("%s: does not document the %r field"
                                    % (name, field))
            if properties.get("schema", {}).get("const") != document["schema"]:
                problems.append("%s: the documented const does not match the schema "
                                "name" % name)
    expected_names = sorted(set(DOCUMENT_SCHEMAS) | set(TREE_SCHEMAS))
    if sorted(set(schema_names)) != expected_names:
        problems.append("schema documents cover %s, expected %s"
                        % (sorted(set(schema_names)), expected_names))

    for rel, schema_name in (("eldunarya/eldunarya.json", "eldunarya-v1"),
                             ("arif/arif.json", "arif-store-v1")):
        template = pc_schema.load_json(
            os.path.join(root, "templates", "protean-context", rel), rel)
        problems.extend(pc_schema.validate(template, pc_paths.schema_document(schema_name),
                                           rel))

    problems.extend(check_ingest(root, bootstrap, adapter, source, pc_schema,
                                 pc_paths))
    problems.extend(check_fixtures(root, pc_schema, pc_paths))

    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("check-schema: PASS")
    print("  json files parsed: %d" % scanned)
    print("  schema documents: %d" % len(schema_names))
    return 0


def check_fixtures(root, pc_schema, pc_paths):
    """Validate the synthetic fixture documents against their own schemas.

    Fixtures are containers: the marker key carries the header, and `document`
    holds the synthetic input. A forward-looking fixture (schemaVersion above
    the shipped version) is left to the migration test that owns it.
    """
    problems = []
    for rel_dir in ("fixtures", "tests/fixtures"):
        base_dir = os.path.join(root, rel_dir)
        if not os.path.isdir(base_dir):
            continue
        for base, dirs, files in os.walk(base_dir):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if not name.endswith(".json"):
                    continue
                full = os.path.join(base, name)
                rel = os.path.relpath(full, root)
                document = pc_schema.load_json(full, rel)
                inner = document
                if isinstance(document, dict) and "document" in document:
                    inner = document["document"]
                if not isinstance(inner, dict):
                    problems.append("%s: fixture holds no document object" % rel)
                    continue
                schema_name = inner.get("schema")
                if schema_name not in pc_paths.SCHEMA_DOCUMENTS:
                    problems.append("%s: fixture declares an unknown schema %r"
                                    % (rel, schema_name))
                    continue
                if inner.get("schemaVersion") != 1:
                    continue
                problems.extend(pc_schema.validate(
                    inner, pc_paths.schema_document(schema_name), rel))
                content = inner.get("content")
                if isinstance(content, dict) and isinstance(content.get("ref"), str):
                    blob = resolve_fixture_ref(full, base_dir, content["ref"])
                    if blob is None:
                        problems.append("%s: content.ref does not resolve inside %s: %s"
                                        % (rel, rel_dir, content["ref"]))
                        continue
                    with open(blob, "rb") as handle:
                        digest = hashlib.sha256(handle.read()).hexdigest()
                    if digest != content.get("checksum"):
                        problems.append("%s: fixture blob checksum mismatch" % rel)
    return problems


def resolve_fixture_ref(full, fixture_root, reference):
    """Resolve a fixture `content.ref` the way the store resolves it.

    The store resolves the ref relative to its own root: a record lives at
    `<store>/records/<id>.json` and carries `content/<sha256>`, which points at
    `<store>/content/<sha256>` (this is exactly what pc_verify checks against a
    real target). A fixture mirrors that layout, so walk up from the record to
    the fixture root and take the first resolution that exists inside it. The
    walk never leaves the fixture tree, and no resolution means a broken pointer.
    """
    directory = os.path.dirname(full)
    stop = os.path.realpath(fixture_root)
    while True:
        candidate = os.path.join(directory, reference)
        if os.path.isfile(candidate):
            return candidate
        if os.path.realpath(directory) == stop:
            return None
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def check_ingest(root, bootstrap, adapter, source, pc_schema, pc_paths):
    """Run the synthetic ingest end to end and validate what it wrote."""
    problems = []
    with tempfile.TemporaryDirectory(prefix="check-schema-") as work:
        target = os.path.join(work, "target")
        commands = [
            [sys.executable, bootstrap, "init", "--target", target, "--name", "demo"],
            [sys.executable, bootstrap, "ingest", "--target", target,
             "--adapter", adapter, "--source", source],
        ]
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True,
                                    cwd=root, timeout=120)
            if result.returncode != 0:
                problems.append("command failed (%s): %s"
                                % (result.returncode, " ".join(command[1:])))
                problems.append((result.stdout + result.stderr).strip()[:400])
                return problems
        records_dir = os.path.join(target, "arif", "records")
        names = sorted(name for name in os.listdir(records_dir)
                       if name.endswith(".json"))
        if not names:
            problems.append("ingest wrote no records")
            return problems
        for name in names:
            rel = "arif/records/%s" % name
            path = os.path.join(records_dir, name)
            document = pc_schema.load_json(path, rel)
            problems.extend(pc_schema.validate(document, pc_paths.schema_document(
                RECORD_SCHEMA), rel))
            content = (document or {}).get("content") or {}
            reference = content.get("ref")
            if not isinstance(reference, str):
                continue
            blob = os.path.join(target, "arif", reference)
            if not os.path.isfile(blob):
                problems.append("%s: content.ref does not resolve: %s" % (rel, reference))
                continue
            with open(blob, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            if digest != content.get("checksum"):
                problems.append("%s: blob checksum mismatch" % rel)
    return problems


if __name__ == "__main__":
    sys.exit(main(sys.argv))
