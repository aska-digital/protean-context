"""ingest: run one explicitly passed adapter and write records plus blobs.

The locked negative contract (decision D4.4): no default source paths, no
scanning of any live tree, no network access, no embedding computation, no
credential access, no import of any adapter not explicitly passed by path, no
background processes. Everything this module reads lives under the explicit
--source or inside --target; everything it writes lives under --target/arif/.

The adapter is one Python module passed with --adapter. It is executed from
its own source in a private namespace (no import machinery, so no third-party
code can be reached), and it must expose ADAPTER_NAME, ADAPTER_VERSION, and
collect(source). collect yields arif-record-v1 shaped dictionaries with a null
embedding. Blob bytes are taken from the explicit --source tree: the declared
content.checksum must match a file under --source (the adapter's own
source.locator is tried first when it is a relative path). An unresolvable
record aborts the run with exit 2 and writes nothing: all or nothing per
invocation.
"""

import json
import os

from pc_common import (EXIT_DEPENDENCY, EXIT_SCHEMA, HEX256_RE, SAFE_SEGMENT_RE,
                       SKIP_DIRS, fail, out, read_bytes, sha256_bytes,
                       sha256_file, write_bytes)
from pc_paths import ARIF_DIR, ARIF_MANIFEST_REL, schema_document
from pc_receipt import read_receipt
from pc_schema import load_json, validate

RECORD_SCHEMA = "arif-record-v1"
ADAPTER_STRING_FIELDS = ("ADAPTER_NAME", "ADAPTER_VERSION")


def load_adapter(path):
    """Execute exactly the adapter file at path and return its namespace."""
    if not os.path.isfile(path):
        fail(EXIT_DEPENDENCY, "adapter missing: %s" % path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
    except OSError as exc:
        fail(EXIT_DEPENDENCY, "adapter unreadable: %s (%s)" % (path, exc))
    namespace = {"__name__": "protean_context_adapter", "__file__": path,
                 "__builtins__": __builtins__}
    try:
        exec(compile(source, path, "exec"), namespace)
    except Exception as exc:
        fail(EXIT_DEPENDENCY, "adapter is not runnable: %s (%s: %s)"
             % (path, type(exc).__name__, exc))
    for field in ADAPTER_STRING_FIELDS:
        value = namespace.get(field)
        if not isinstance(value, str) or not value:
            fail(EXIT_DEPENDENCY, "adapter does not expose a non-empty %s string"
                 % field)
    if not callable(namespace.get("collect")):
        fail(EXIT_DEPENDENCY, "adapter does not expose collect(source)")
    return namespace


def collect_records(namespace, source):
    path = namespace.get("__file__")
    try:
        yielded = namespace["collect"](source)
    except Exception as exc:
        fail(EXIT_DEPENDENCY, "adapter collect() failed (%s: %s)"
             % (type(exc).__name__, exc))
    records = []
    try:
        for item in yielded:
            records.append(item)
    except Exception as exc:
        fail(EXIT_DEPENDENCY, "adapter iteration failed (%s: %s)"
             % (type(exc).__name__, exc))
    return records, path


def check_record(record, label, problems):
    """Record-shape checks the schema cannot express (ids, refs, confinement)."""
    if not isinstance(record, dict):
        problems.append("%s: record is not an object" % label)
        return
    problems.extend(validate(record, schema_document(RECORD_SCHEMA), label))
    identifier = record.get("id")
    if isinstance(identifier, str) and not SAFE_SEGMENT_RE.match(identifier):
        problems.append("%s: id %r is not a single safe path segment" % (label, identifier))
    content = record.get("content") or {}
    if isinstance(content, dict):
        checksum = content.get("checksum")
        reference = content.get("ref")
        if isinstance(checksum, str) and not HEX256_RE.match(checksum):
            problems.append("%s: content.checksum is not a 64-character sha256" % label)
        if isinstance(checksum, str) and reference != "content/%s" % checksum:
            problems.append("%s: content.ref must be content/<sha256>" % label)
    if record.get("embedding") is not None:
        problems.append("%s: embedding must be null (the scaffold computes none)" % label)


def resolve_blob(source, record, label, problems):
    """Bytes for one record, read only inside --source."""
    content = record.get("content") or {}
    checksum = content.get("checksum")
    if not isinstance(checksum, str) or not HEX256_RE.match(checksum):
        return None
    locator = (record.get("source") or {}).get("locator")
    candidates = []
    if os.path.isfile(source):
        candidates.append(source)
    if isinstance(locator, str) and locator and "://" not in locator \
            and not locator.startswith("/"):
        candidate = os.path.join(source, locator)
        if os.path.isfile(candidate):
            candidates.append(candidate)
    for candidate in candidates:
        if sha256_file(candidate) == checksum:
            return read_bytes(candidate)
    if os.path.isdir(source):
        for base, dirs, files in os.walk(source):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                candidate = os.path.join(base, name)
                if sha256_file(candidate) == checksum:
                    return read_bytes(candidate)
    problems.append("%s: no file under --source matches content.checksum %s"
                    % (label, checksum))
    return None


def run(target, adapter_path, source, dry_run=False):
    """Run ingest; return the process exit code."""
    if not os.path.isdir(target):
        fail(EXIT_DEPENDENCY, "target is not an initialized directory: %s" % target)
    if read_receipt(target) is None:
        fail(EXIT_DEPENDENCY, "target has no init receipt: run init first (%s)" % target)
    manifest_path = os.path.join(target, ARIF_MANIFEST_REL)
    if not os.path.isfile(manifest_path):
        fail(EXIT_DEPENDENCY, "missing prerequisite: %s" % ARIF_MANIFEST_REL)
    manifest = load_json(manifest_path, ARIF_MANIFEST_REL)
    if not os.path.isdir(source):
        if not os.path.isfile(source):
            fail(EXIT_DEPENDENCY, "missing prerequisite: --source %s does not exist"
                 % source)
    namespace = load_adapter(adapter_path)
    records, _adapter_file = collect_records(namespace, source)
    problems = []
    seen = {}
    blobs = {}
    for index, record in enumerate(records):
        label = "%s record[%d]" % (namespace["ADAPTER_NAME"], index)
        check_record(record, label, problems)
        if not isinstance(record, dict):
            continue
        identifier = record.get("id")
        if isinstance(identifier, str):
            if identifier in seen:
                problems.append("%s: duplicate id %r in one invocation"
                                % (label, identifier))
            seen[identifier] = True
        data = resolve_blob(source, record, label, problems)
        if data is not None:
            checksum = (record.get("content") or {}).get("checksum")
            if (record.get("content") or {}).get("bytes") != len(data):
                problems.append("%s: content.bytes does not match the source bytes"
                                % label)
            blobs[checksum] = data
    if problems:
        fail(EXIT_SCHEMA, "ingest aborted, nothing was written: %s"
             % "; ".join(problems))
    out("target: %s" % target)
    out("adapter: %s %s" % (namespace["ADAPTER_NAME"], namespace["ADAPTER_VERSION"]))
    out("source: %s" % source)
    out("records: %d" % len(records))
    for record in records:
        checksum = (record.get("content") or {}).get("checksum")
        out("%s%s: %s/%s" % ("would write: " if dry_run else "write: ",
                             ARIF_DIR, "content", checksum))
        out("%s%s: records/%s.json" % ("would write: " if dry_run else "write: ",
                                       ARIF_DIR, record.get("id")))
    if dry_run:
        out("result: dry-run, no files written")
        return 0
    for checksum in sorted(blobs):
        write_bytes(os.path.join(target, ARIF_DIR, "content", checksum), blobs[checksum])
    for record in records:
        text = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
        write_bytes(os.path.join(target, ARIF_DIR, "records",
                                 "%s.json" % record["id"]), text.encode("utf-8"))
    out("summary: records=%d blobs=%d" % (len(records), len(blobs)))
    out("result: ok")
    return 0
