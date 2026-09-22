"""Shared helpers for the behavioral tests. Stdlib only, no live state.

Every helper works on explicit temporary directories; nothing here reads or
writes outside the directory it is given.
"""

import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts", "protean-context")
BOOTSTRAP = os.path.join(SCRIPTS, "bootstrap.py")
ADAPTER = os.path.join(ROOT, "tests", "fixtures", "adapter_synthetic.py")
SOURCE = os.path.join(ROOT, "tests", "fixtures", "source")
MIGRATION_FIXTURES = os.path.join(ROOT, "tests", "fixtures", "migration")
RECEIPT = ".protean-context-receipt.json"
SKIP_NAMES = ("__pycache__", ".protean-backup")


def run_cli(*args, **kwargs):
    """Run the CLI as a subprocess and return the completed process."""
    env = kwargs.pop("env", None)
    cwd = kwargs.pop("cwd", ROOT)
    timeout = kwargs.pop("timeout", 120)
    return subprocess.run([sys.executable, BOOTSTRAP] + [str(item) for item in args],
                          capture_output=True, text=True, cwd=cwd, env=env,
                          timeout=timeout)


def run_gate(relative_path, *args, **kwargs):
    return subprocess.run([sys.executable, os.path.join(ROOT, relative_path)]
                          + [str(item) for item in args],
                          capture_output=True, text=True, cwd=kwargs.get("cwd", ROOT),
                          timeout=kwargs.get("timeout", 300))


def file_map(root):
    """{relative path: sha256} for every file under root."""
    found = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES)
        for name in sorted(files):
            if name.endswith(".pyc"):
                continue
            full = os.path.join(base, name)
            with open(full, "rb") as handle:
                found[os.path.relpath(full, root)] = hashlib.sha256(
                    handle.read()).hexdigest()
    return found


def tree_digest(root):
    """One digest over the sorted (relative path, sha256) pairs of a tree."""
    digest = hashlib.sha256()
    mapping = file_map(root)
    for rel in sorted(mapping):
        digest.update(rel.encode("utf-8") + b"\x00")
        digest.update(mapping[rel].encode("utf-8") + b"\n")
    return digest.hexdigest()


def mtimes(root):
    found = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES)
        for name in sorted(files):
            full = os.path.join(base, name)
            found[os.path.relpath(full, root)] = os.stat(full).st_mtime_ns
    return found


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def load_json(path):
    """Parse one JSON document under a test's temporary tree."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dumps_json(document):
    """Render a document exactly the way the scaffold renders its JSON files."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def fixture_document(path):
    """Load a synthetic fixture container and return its `document`."""
    with open(path, "r", encoding="utf-8") as handle:
        container = json.load(handle)
    if "SYNTHETIC TEST DATA" not in container:
        raise AssertionError("fixture is not marked as synthetic: %s" % path)
    return container["document"]
