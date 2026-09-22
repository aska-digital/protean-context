#!/usr/bin/env python3
"""check-path-portability.py - gate 5 of build/verify-all.py.

Proves the token discipline:

  * only `{HOME}`, `{TARGET}`, `{HERMES_HOME}`, `{PROFILE_NAME}`, and the single
    materialization placeholder `{ELDUNARI_NAME}` appear as `{TOKEN}` forms;
  * no bare `~` is used as a path anywhere;
  * no shipped JSON carries an absolute path as a value;
  * the standalone installer starts with an empty target and therefore requires
    `--target` instead of defaulting to a machine path.

Usage: python3 gates/protean-context/check-path-portability.py [repo-root]
Exit: 0 pass; 1 violation; 2 missing source data.
"""

import json
import os
import re
import sys

GATE = "check-path-portability.py"
SKIP_DIRS = (".git", "__pycache__", ".protean-backup")
TEXT_EXT = (".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt", "")
ALLOWED_TOKENS = ("HOME", "TARGET", "HERMES_HOME", "PROFILE_NAME", "ELDUNARI_NAME")
TOKEN_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
TILDE_RE = re.compile(r"(^|[\s'\"=(:,])~(/|\s|$)")
TARGET_DEFAULT_RE = re.compile(r'^TARGET="(.*)"\s*$', re.MULTILINE)


def iter_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            full = os.path.join(base, name)
            yield os.path.relpath(full, root), full


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    installer = os.path.join(root, "install.sh")
    if not os.path.isfile(os.path.join(root, "README.md")):
        sys.stderr.write("MISSING: README.md\n")
        return 2
    if not os.path.isfile(installer):
        sys.stderr.write("MISSING: install.sh\n")
        return 2

    problems = []
    scanned = 0
    for rel, path in iter_files(root):
        if os.path.basename(rel) == GATE or rel.endswith((".pyc", ".png", ".pdf")):
            continue
        if os.path.splitext(rel)[1] not in TEXT_EXT:
            continue
        scanned += 1
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for match in TOKEN_RE.finditer(line):
                if match.group(1) not in ALLOWED_TOKENS:
                    problems.append("%s:%d: placeholder token {%s} is outside the "
                                    "allowed token set" % (rel, number, match.group(1)))
            if TILDE_RE.search(line):
                problems.append("%s:%d: bare ~ used as a path" % (rel, number))
        if rel.endswith(".json"):
            problems.extend(check_json_values(rel, text))

    with open(installer, "r", encoding="utf-8") as handle:
        installer_text = handle.read()
    match = TARGET_DEFAULT_RE.search(installer_text)
    if not match:
        problems.append("install.sh: does not initialise TARGET to an empty value")
    elif match.group(1) != "":
        problems.append("install.sh: TARGET defaults to %r; --target must be required"
                        % match.group(1))

    if scanned == 0:
        sys.stderr.write("MISSING: no files to scan under %s\n" % root)
        return 2
    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("check-path-portability: PASS")
    print("  files scanned: %d" % scanned)
    print("  allowed tokens: %s" % ", ".join("{%s}" % token
                                             for token in ALLOWED_TOKENS))
    return 0


def check_json_values(rel, text):
    """No shipped JSON carries an absolute path or a bare ~ as a value."""
    problems = []
    try:
        document = json.loads(text)
    except ValueError:
        return problems
    for path, value in walk_values(document):
        if not isinstance(value, str):
            continue
        if value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value):
            problems.append("%s: %s carries the absolute path %r as a value"
                            % (rel, path, value))
        if value.startswith("~"):
            problems.append("%s: %s carries a bare ~ path %r" % (rel, path, value))
    return problems


def walk_values(node, prefix=""):
    pairs = []
    if isinstance(node, dict):
        for key in sorted(node):
            pairs.extend(walk_values(node[key], "%s.%s" % (prefix, key)))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            pairs.extend(walk_values(item, "%s[%d]" % (prefix, index)))
    else:
        pairs.append((prefix, node))
    return pairs


if __name__ == "__main__":
    sys.exit(main(sys.argv))
