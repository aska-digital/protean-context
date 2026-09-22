"""Init receipt for the protean-context scaffold (schema protean-context-receipt-v1).

The receipt is the only record of what init created. `remove` deletes exactly
those paths, and only while their current hash still matches, so a file the
user modified survives. The receipt carries no timestamps and no absolute
paths, so two identical inits produce identical receipts (determinism).
"""

import json
import os

from pc_common import (EXIT_SCHEMA, fail, iter_rel_files, read_text, sha256_file,
                       write_text)

RECEIPT_NAME = ".protean-context-receipt.json"
RECEIPT_SCHEMA = "protean-context-receipt-v1"
RECEIPT_VERSION = 1


def receipt_path(target):
    return os.path.join(target, RECEIPT_NAME)


def read_receipt(target):
    """Return the receipt document, or None when the target has no receipt yet."""
    path = receipt_path(target)
    if not os.path.isfile(path):
        return None
    try:
        document = json.loads(read_text(path))
    except ValueError as exc:
        fail(EXIT_SCHEMA, "invalid receipt: %s is not valid JSON (%s)"
             % (RECEIPT_NAME, exc))
    if not isinstance(document, dict):
        fail(EXIT_SCHEMA, "invalid receipt: %s is not an object" % RECEIPT_NAME)
    if document.get("schema") != RECEIPT_SCHEMA:
        fail(EXIT_SCHEMA, "invalid receipt: schema is %r, expected %r"
             % (document.get("schema"), RECEIPT_SCHEMA))
    if document.get("schemaVersion") != RECEIPT_VERSION:
        fail(EXIT_SCHEMA, "invalid receipt: schemaVersion is %r, expected %r"
             % (document.get("schemaVersion"), RECEIPT_VERSION))
    return document


def build_receipt(created, directories, migrations=None):
    """Build the receipt document. created maps relative path to sha256."""
    entries = [{"path": rel, "sha256": created[rel]} for rel in sorted(created)]
    return {
        "schema": RECEIPT_SCHEMA,
        "schemaVersion": RECEIPT_VERSION,
        "created": entries,
        "directories": sorted(set(directories)),
        "migrations": list(migrations or []),
    }


def render_receipt(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def write_receipt(target, document):
    """Write the receipt (always last) and return its rendered text."""
    text = render_receipt(document)
    write_text(receipt_path(target), text)
    return text


def created_hashes(document):
    """The receipt's {relative path: sha256} view."""
    result = {}
    for entry in document.get("created") or []:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            result[entry["path"]] = entry.get("sha256")
    return result


def receipt_directories(document):
    return [item for item in (document.get("directories") or [])
            if isinstance(item, str)]


def target_files(target):
    """Files currently present under target, minus the receipt itself."""
    return [rel for rel in iter_rel_files(target) if rel != RECEIPT_NAME]


def current_hashes(target):
    return {rel: sha256_file(os.path.join(target, rel))
            for rel in target_files(target)}
