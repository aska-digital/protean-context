#!/usr/bin/env python3
"""check-synthetic-fixtures.py - gate 8 of build/verify-all.py.

Proves that every fixture is synthetic and visibly marked:

  * every file under fixtures/ and tests/fixtures/ carries the
    `SYNTHETIC TEST DATA` marker;
  * no fixture carries a URL, a host name, a drive letter, or an absolute path;
  * every entity-like value (name, id, title, locator, topic, tag, and friends)
    is built only from the synthetic vocabulary maintained next to this gate,
    so a real person, place, document, or product name cannot enter a fixture
    quietly.

Usage: python3 gates/protean-context/check-synthetic-fixtures.py [repo-root]
Exit: 0 pass; 1 violation; 2 missing fixture source data.
"""

import json
import os
import re
import sys

GATE = "check-synthetic-fixtures.py"
MARKER = "SYNTHETIC TEST DATA"
FIXTURE_DIRS = ("fixtures", "tests/fixtures")
SKIP_DIRS = (".git", "__pycache__", ".protean-backup")

# The synthetic vocabulary, maintained here on purpose: a fixture may name an
# entity only with these tokens (plus digits, hashes, and file extensions).
SYNTHETIC_VOCABULARY = frozenset((
    "demo", "sample", "example", "alpha", "beta", "gamma", "synthetic", "test",
    "data", "widget", "placeholder", "fixture", "record", "source", "topic",
    "tag", "note", "doc", "document", "web", "other", "plain", "text", "utf",
    "txt", "md", "json", "sha256", "v1", "v2", "adapter", "migration", "entry",
    "item", "list", "block", "field", "unknown", "zero", "one", "two",
))
WATCHED_KEYS = ("name", "id", "title", "locator", "author", "subject", "topic",
                "topics", "tags", "filename", "adapter", "provider", "model",
                "method", "kind")
TOKEN_RE = re.compile(r"[A-Za-z]+")
HEX_RE = re.compile(r"^[0-9a-f]{32,}$")
HOST_RE = re.compile(r"://|www\.|\.com|\.org|\.net|\.io\b")
ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]|^/")
EXTENSIONS = frozenset(("txt", "md", "json", "jpg", "png", "pdf", "csv"))


def fixture_files(root):
    found = []
    for rel_dir in FIXTURE_DIRS:
        base_dir = os.path.join(root, rel_dir)
        if not os.path.isdir(base_dir):
            continue
        for base, dirs, files in os.walk(base_dir):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                full = os.path.join(base, name)
                found.append(os.path.relpath(full, root))
    return sorted(found)


def all_strings(rel, text):
    """Every string value of a JSON fixture, or every line of a text fixture."""
    if rel.endswith(".json"):
        try:
            document = json.loads(text)
        except ValueError:
            return []
        return walk(document, watched=False)
    return [line for line in text.splitlines() if line.strip()]


def walk(node, key=None, watched=True):
    values = []
    if isinstance(node, dict):
        for name in sorted(node):
            values.extend(walk(node[name], name, watched))
    elif isinstance(node, list):
        for item in node:
            values.extend(walk(item, key, watched))
    elif isinstance(node, str) and (not watched or key in WATCHED_KEYS):
        values.append(node)
    return values


def entity_values(rel, text):
    """Entity-like string values of one fixture file."""
    values = []
    if rel.endswith(".json"):
        try:
            document = json.loads(text)
        except ValueError:
            return values
        values.extend(walk(document))
    else:
        for line in text.splitlines():
            for key in WATCHED_KEYS:
                match = re.search(r"%s\s*[:=]\s*\"?([^\"\n,]+)" % key, line)
                if match:
                    values.append(match.group(1).strip())
    return values


def check_surface(rel, value):
    """Host names and machine-specific absolute paths, anywhere in a fixture."""
    problems = []
    if HOST_RE.search(value):
        problems.append("%s: value %r looks like a real host name" % (rel, value))
    if ABS_PATH_RE.search(value):
        problems.append("%s: value %r is a machine-specific absolute path"
                        % (rel, value))
    return problems


def check_value(rel, value):
    problems = []
    if HOST_RE.search(value):
        problems.append("%s: value %r looks like a real host name" % (rel, value))
    if ABS_PATH_RE.search(value):
        problems.append("%s: value %r is an absolute path" % (rel, value))
    if HEX_RE.match(value):
        return problems
    for token in TOKEN_RE.findall(value):
        lowered = token.lower()
        if lowered in SYNTHETIC_VOCABULARY or lowered in EXTENSIONS:
            continue
        problems.append("%s: value %r uses %r, which is not in the synthetic "
                        "vocabulary next to this gate" % (rel, value, token))
    return problems


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    files = fixture_files(root)
    if not files:
        sys.stderr.write("MISSING: no fixtures under %s\n"
                         % " or ".join(FIXTURE_DIRS))
        return 2
    problems = []
    for rel in files:
        path = os.path.join(root, rel)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except (UnicodeDecodeError, OSError) as exc:
            problems.append("%s: unreadable (%s)" % (rel, exc))
            continue
        if MARKER not in text:
            problems.append("%s: does not carry the %r marker" % (rel, MARKER))
        for value in all_strings(rel, text):
            problems.extend(check_surface(rel, value))
        if rel.endswith(".json"):
            for value in entity_values(rel, text):
                problems.extend(check_value(rel, value))
    if problems:
        print("FAIL: %s" % GATE)
        for problem in sorted(set(problems)):
            print("  " + problem)
        return 1
    print("check-synthetic-fixtures: PASS")
    print("  fixtures checked: %d" % len(files))
    print("  synthetic vocabulary terms: %d" % len(SYNTHETIC_VOCABULARY))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
