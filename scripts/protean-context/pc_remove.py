"""remove: delete exactly what init created, and only while it is unmodified.

Semantics (locked, decision D5.4): `remove` deletes exactly the receipt-listed
paths whose current hash still matches; a receipt-listed path whose hash
differs (the user modified it) is skipped and reported; unlisted files are
never touched; directories are removed only when empty; the receipt is deleted
last. `remove --dry-run` prints the same plan without deleting anything.
"""

import os

from pc_common import EXIT_SCHEMA, fail, out, sha256_file
from pc_receipt import (created_hashes, receipt_directories, receipt_path,
                        read_receipt)

SKIP_REASON = "user-modified"


def deepest_first(paths):
    return sorted(paths, key=lambda item: (-item.count("/"), item))


def plan_removal(target, document):
    """Classify every receipt-listed path without deleting anything."""
    hashes = created_hashes(document)
    removable, skipped, absent = [], [], []
    for rel in deepest_first(list(hashes)):
        path = os.path.join(target, rel)
        if not os.path.exists(path):
            absent.append(rel)
            continue
        if not os.path.isfile(path):
            skipped.append((rel, "no longer a regular file"))
            continue
        if sha256_file(path) == hashes[rel]:
            removable.append(rel)
        else:
            skipped.append((rel, SKIP_REASON))
    directories = [rel for rel in deepest_first(receipt_directories(document))
                   if os.path.isdir(os.path.join(target, rel))]
    return {"removable": removable, "skipped": skipped, "absent": absent,
            "directories": directories}


def run(target, dry_run=False):
    """Run remove; return the process exit code."""
    document = read_receipt(target)
    if document is None:
        fail(EXIT_SCHEMA, "no init receipt at %s: remove is scoped to what init "
                          "created, so there is nothing it may delete" % target)
    plan = plan_removal(target, document)
    out("target: %s" % target)
    out("command: %s" % ("remove (dry-run)" if dry_run else "remove"))
    out("receipt: %s" % receipt_path(target))
    for rel in plan["removable"]:
        out("%s: %s" % ("would delete" if dry_run else "delete", rel))
    for rel, reason in plan["skipped"]:
        out("skipped: %s (%s)" % (rel, reason))
    for rel in plan["absent"]:
        out("absent: %s (already gone)" % rel)
    if dry_run:
        out("summary: delete=%d skipped=%d absent=%d directories=%d"
            % (len(plan["removable"]), len(plan["skipped"]), len(plan["absent"]),
               len(plan["directories"])))
        out("result: dry-run, no files deleted")
        return 0
    deleted = 0
    for rel in plan["removable"]:
        path = os.path.join(target, rel)
        try:
            os.remove(path)
            deleted += 1
            out("deleted: %s" % rel)
        except OSError as exc:
            out("kept: %s (delete failed: %s)" % (rel, exc))
    removed_dirs = 0
    for rel in plan["directories"]:
        path = os.path.join(target, rel)
        if not os.path.isdir(path):
            continue
        try:
            os.rmdir(path)
            removed_dirs += 1
            out("removed directory: %s" % rel)
        except OSError:
            out("kept directory: %s (not empty)" % rel)
    receipt = receipt_path(target)
    if os.path.isfile(receipt):
        try:
            os.remove(receipt)
            out("deleted: %s" % os.path.basename(receipt))
        except OSError as exc:
            out("kept: %s (delete failed: %s)" % (os.path.basename(receipt), exc))
    out("summary: delete=%d skipped=%d absent=%d directories=%d"
        % (deleted, len(plan["skipped"]), len(plan["absent"]), removed_dirs))
    out("result: ok")
    return 0
