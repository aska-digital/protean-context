"""Shared helpers for the protean-context bootstrap CLI.

Stdlib only. No network. No live-state reads: every command works on an
explicit --target (and, for ingest, an explicit --source).
"""

import hashlib
import os
import re
import sys
from typing import NoReturn

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_SCHEMA = 2
EXIT_DEPENDENCY = 3
EXIT_INTEGRITY = 4
EXIT_INSTALL = 5
EXIT_VERIFY = 6

EXIT_MEANINGS = {
    EXIT_OK: "ok",
    EXIT_USAGE: "usage, bad --name, reserved name",
    EXIT_SCHEMA: "schema, manifest, or registry invalid; downgrade refused",
    EXIT_DEPENDENCY: "adapter missing or unimportable; missing prerequisite",
    EXIT_INTEGRITY: "hash mismatch, conflict on a scaffold file",
    EXIT_INSTALL: "write failure (permissions, full disk)",
    EXIT_VERIFY: "verify found a failing or skipping check",
}

# Locked naming rule (architecture decision D3.4): 1 to 48 characters,
# lowercase, digits, inner hyphens, no leading or trailing hyphen.
NAME_RE = re.compile(r"^[a-z]([a-z0-9-]{0,46}[a-z0-9])?$")

# Reserved names are rejected because they collide with the tree's own
# directory vocabulary.
RESERVED_NAMES = ("eldunari", "eldunarya", "arif")

# A record id becomes a single file name inside records/.
SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
HEX256_RE = re.compile(r"^[0-9a-f]{64}$")

SKIP_DIRS = (".git", "__pycache__", ".protean-backup")


class BootstrapError(Exception):
    """A command failure that carries the CLI exit code."""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code
        self.message = message


def fail(code, message) -> "NoReturn":
    raise BootstrapError(code, message)


def err(message):
    """Errors go to stderr (kit convention)."""
    sys.stderr.write("error: %s\n" % message)


def out(message):
    """The summary goes to stdout (kit convention)."""
    sys.stdout.write("%s\n" % message)


def check_name(name):
    """Validate one --name value; exit 1 on a bad or reserved name."""
    if not isinstance(name, str) or not NAME_RE.match(name):
        fail(EXIT_USAGE,
             "bad --name: %r does not match ^[a-z]([a-z0-9-]{0,46}[a-z0-9])?$" % (name,))
    if name in RESERVED_NAMES:
        fail(EXIT_USAGE, "reserved --name: %r is part of the tree vocabulary" % (name,))
    return name


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_bytes(path, data):
    """Write bytes and read them back; a mismatch is a write failure (exit 5)."""
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "wb") as handle:
            handle.write(data)
    except OSError as exc:
        fail(EXIT_INSTALL, "write failed: %s (%s)" % (path, exc))
    readback = sha256_file(path)
    if readback != sha256_bytes(data):
        fail(EXIT_INSTALL, "read-back mismatch after writing %s" % path)
    return readback


def write_text(path, text):
    return write_bytes(path, text.encode("utf-8"))


def rel_posix(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def iter_rel_files(root):
    """Every file under root, as sorted relative posix paths."""
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(".pyc"):
                continue
            full = os.path.join(base, name)
            if os.path.isfile(full):
                found.append(rel_posix(root, full))
    return sorted(found)


def tree_digest(root):
    """One digest over sorted (relative path, sha256) pairs."""
    digest = hashlib.sha256()
    for rel in iter_rel_files(root):
        digest.update(rel.encode("utf-8") + b"\x00")
        digest.update(sha256_file(os.path.join(root, rel)).encode("utf-8") + b"\n")
    return digest.hexdigest()


def require_network(offline, reason):
    """Refuse any code path that would need network access.

    Nothing in v1.0.0 calls this: the scaffold has no network path at all.
    It exists so that a future path cannot be added silently, and so that
    --offline is a refusal rather than a label.
    """
    if offline:
        fail(EXIT_DEPENDENCY,
             "refused under --offline: this code path would need network access (%s)"
             % reason)
    fail(EXIT_DEPENDENCY,
         "network access is not available in this scaffold (%s)" % reason)


def is_within(path, root):
    """True when path (resolved) sits inside root (resolved)."""
    target = os.path.realpath(path)
    base = os.path.realpath(root)
    return target == base or target.startswith(base + os.sep)
