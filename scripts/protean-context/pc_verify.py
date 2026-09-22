"""verify: check an initialized target against the scaffold contract.

`verify` never reads anything outside --target except the scaffold's own code
and shipped schema documents, and it writes nothing at all. A check that
cannot be evaluated is a failure, not a pass, so a partially readable target
exits 6 (decision D5.5).
"""

import os

from pc_common import EXIT_VERIFY, HEX256_RE, NAME_RE, out, sha256_file
from pc_paths import (ARIF_ADAPTERS_README_REL, ARIF_EMPTY_DIRS, ARIF_MANIFEST_REL,
                      ELDUNARYA_DIR, REGISTRY_REL, modules_path,
                      modules_readme_path, registry_entry_path,
                      registry_entry_router, schema_document)
from pc_receipt import RECEIPT_NAME, created_hashes, receipt_directories, read_receipt
from pc_schema import load_json, validate

REGISTRY_SCHEMA = "eldunarya-v1"
ARIF_SCHEMA = "arif-store-v1"
RECORD_SCHEMA = "arif-record-v1"


def schema_problems(document, schema_name, label):
    return validate(document, schema_document(schema_name), label)


def check_receipt(target, problems):
    document = read_receipt(target)
    if document is None:
        problems.append("%s: missing (run init first; verify is scoped to an "
                        "initialized target)" % RECEIPT_NAME)
        return
    hashes = created_hashes(document)
    for rel in sorted(hashes):
        if not os.path.isfile(os.path.join(target, rel)):
            problems.append("%s: receipted path is missing: %s" % (RECEIPT_NAME, rel))
    for rel in receipt_directories(document):
        if not os.path.isdir(os.path.join(target, rel)):
            problems.append("%s: receipted directory is missing: %s"
                            % (RECEIPT_NAME, rel))


def check_registry(target, problems):
    path = os.path.join(target, REGISTRY_REL)
    if not os.path.isfile(path):
        problems.append("%s: missing" % REGISTRY_REL)
        return
    document = load_json(path, REGISTRY_REL)
    problems.extend(schema_problems(document, REGISTRY_SCHEMA, REGISTRY_REL))
    names = []
    for index, entry in enumerate(document.get("eldunari") or []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        names.append(name)
        where = "%s[%s]" % (REGISTRY_REL, name)
        if not NAME_RE.match(name) or name in ("eldunari", "eldunarya", "arif"):
            problems.append("%s: name does not follow the naming rule" % where)
        expected_path = registry_entry_path(name)
        expected_router = registry_entry_router(name)
        if entry.get("path") != expected_path:
            problems.append("%s: path is %r, expected %r"
                            % (where, entry.get("path"), expected_path))
        if entry.get("router") != expected_router:
            problems.append("%s: router is %r, expected %r"
                            % (where, entry.get("router"), expected_router))
        router_file = os.path.join(target, ELDUNARYA_DIR, expected_router)
        if not os.path.isfile(router_file):
            problems.append("%s: pointer does not resolve: %s"
                            % (where, expected_router))
        if not os.path.isdir(os.path.join(target, modules_path(name))):
            problems.append("%s: pointer does not resolve: %s"
                            % (where, modules_path(name)))
        readme = modules_readme_path(name)
        if not os.path.isfile(os.path.join(target, readme)):
            problems.append("%s: pointer does not resolve: %s" % (where, readme))
        problems.extend(check_tree(target, name))
    if not names:
        problems.append("%s: the registry lists no Eldunari" % REGISTRY_REL)


def check_tree(target, name):
    """Shape of one Eldunari tree, validated against the eldunari-v1 schema."""
    modules = os.path.join(target, modules_path(name))
    files = []
    if os.path.isdir(modules):
        for item in sorted(os.listdir(modules)):
            if item == "README.md" or item.startswith("."):
                continue
            if os.path.isfile(os.path.join(modules, item)):
                files.append(item)
    document = {
        "router": "ROUTER.md" if os.path.isfile(
            os.path.join(target, router_file_rel(name))) else "MISSING",
        "modules": {
            "stub": "README.md" if os.path.isfile(
                os.path.join(target, modules_readme_path(name))) else "MISSING",
            "files": files,
        },
    }
    return schema_problems(document, "eldunari-v1", "eldunari/%s tree" % name)


def router_file_rel(name):
    return "%s/%s" % (ELDUNARYA_DIR, registry_entry_router(name))


def check_arif(target, problems):
    path = os.path.join(target, ARIF_MANIFEST_REL)
    if not os.path.isfile(path):
        problems.append("%s: missing" % ARIF_MANIFEST_REL)
        return
    manifest = load_json(path, ARIF_MANIFEST_REL)
    problems.extend(schema_problems(manifest, ARIF_SCHEMA, ARIF_MANIFEST_REL))
    for rel in ARIF_EMPTY_DIRS:
        if not os.path.isdir(os.path.join(target, rel)):
            problems.append("%s: missing directory" % rel)
    if not os.path.isfile(os.path.join(target, ARIF_ADAPTERS_README_REL)):
        problems.append("%s: missing" % ARIF_ADAPTERS_README_REL)
    embedding = manifest.get("embedding") or {}
    enabled = bool(embedding.get("enabled"))
    if enabled:
        return
    index_rel = "arif/index"
    if os.path.isdir(os.path.join(target, index_rel)):
        for name in sorted(os.listdir(os.path.join(target, index_rel))):
            problems.append("%s: embedding is disabled but the index holds %s"
                            % (index_rel, name))
    check_records(target, problems, enabled=False)


def check_records(target, problems, enabled):
    records_dir = os.path.join(target, "arif/records")
    if not os.path.isdir(records_dir):
        return
    for name in sorted(os.listdir(records_dir)):
        if name.startswith("."):
            continue
        rel = "arif/records/%s" % name
        if not name.endswith(".json"):
            problems.append("%s: not a record file (records are one JSON file each)"
                            % rel)
            continue
        record = load_json(os.path.join(target, rel), rel)
        problems.extend(schema_problems(record, RECORD_SCHEMA, rel))
        if not isinstance(record, dict):
            continue
        if not enabled and record.get("embedding") is not None:
            problems.append("%s: embedding is disabled but the record carries one"
                            % rel)
        content = record.get("content") or {}
        ref = content.get("ref")
        checksum = content.get("checksum")
        if not isinstance(ref, str) or not isinstance(checksum, str):
            continue
        if not HEX256_RE.match(checksum):
            problems.append("%s: content.checksum is not a sha256" % rel)
            continue
        if ref != "content/%s" % checksum:
            problems.append("%s: content.ref %r is not content/<sha256>" % (rel, ref))
        blob = os.path.join(target, "arif", ref)
        if not os.path.isfile(blob):
            problems.append("%s: content.ref does not resolve inside content/: %s"
                            % (rel, ref))
            continue
        if sha256_file(blob) != checksum:
            problems.append("%s: blob checksum mismatch for %s" % (rel, ref))
        if isinstance(content.get("bytes"), int) and not isinstance(
                content.get("bytes"), bool):
            if os.path.getsize(blob) != content["bytes"]:
                problems.append("%s: content.bytes does not match the stored blob"
                                % rel)


CHECKS = (
    ("receipt", check_receipt),
    ("eldunarya-registry", check_registry),
    ("arif-store", check_arif),
)


def run(target):
    """Run every target check; return 0 when all pass, 6 otherwise."""
    problems = []
    if not os.path.isdir(target):
        problems.append("target does not exist or is not a directory: %s" % target)
        lines = []
    else:
        lines = []
        for name, function in CHECKS:
            found = []
            function(target, found)
            lines.append((name, found))
            problems.extend(found)
    out("target: %s" % target)
    for name, found in lines:
        out("check %s: %s" % (name, "ok" if not found else "FAILED"))
    for problem in problems:
        out("problem: %s" % problem)
    out("checks: %d failed=%d" % (len(lines), len(problems)))
    if problems:
        out("result: failed (%d problem(s))" % len(problems))
        return EXIT_VERIFY
    out("result: ok")
    return 0
