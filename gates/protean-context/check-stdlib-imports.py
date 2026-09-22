#!/usr/bin/env python3
"""check-stdlib-imports.py - gate 7 of build/verify-all.py.

Proves the stdlib-only rule by AST instead of trust:

  * every `import` and `from ... import` in every Python file of this tree is
    read from the syntax tree, so a hidden or dynamic import cannot slip past;
  * a module outside the frozen allowlist is a failure, named;
  * network modules are hard-forbidden;
  * the scaffold's own sibling modules (a `.py` file of the same name shipped
    in this tree) are allowed, which is how the CLI is split into modules.

Frozen allowlist (architecture decision D6 of the protean-context lock
(2026-09-22)): argparse, ast, datetime, fnmatch, hashlib, json, os, pathlib,
re, shutil, subprocess, sys, tempfile, textwrap, typing, unittest.

Usage: python3 gates/protean-context/check-stdlib-imports.py [repo-root]
Exit: 0 pass; 1 violation; 2 missing source data.
"""

import ast
import os
import sys

GATE = "check-stdlib-imports.py"
SKIP_DIRS = (".git", "__pycache__", ".protean-backup")
ALLOWED = frozenset((
    "argparse", "ast", "datetime", "fnmatch", "hashlib", "json", "os", "pathlib",
    "re", "shutil", "subprocess", "sys", "tempfile", "textwrap", "typing",
    "unittest",
))
FORBIDDEN = frozenset((
    "socket", "socketserver", "ssl", "urllib", "urllib2", "urllib3", "http",
    "httplib", "ftplib", "smtplib", "telnetlib", "xmlrpc", "requests",
    "aiohttp", "paramiko", "webbrowser",
))


def python_files(root):
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(".py"):
                found.append(os.path.relpath(os.path.join(base, name), root))
    return sorted(found)


def imported_names(tree):
    """Every imported module root, with the line that imported it."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name.split(".")[0], node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                found.append((node.module.split(".")[0], node.lineno, node.module))
    return found


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    if not os.path.isfile(os.path.join(root, "README.md")):
        sys.stderr.write("MISSING: README.md\n")
        return 2
    files = python_files(root)
    if not files:
        sys.stderr.write("MISSING: no Python files under %s\n" % root)
        return 2
    local = set(os.path.splitext(os.path.basename(rel))[0] for rel in files)
    problems = []
    checked = 0
    modules_seen = set()
    dynamic = []
    for rel in files:
        path = os.path.join(root, rel)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=rel)
        except (SyntaxError, ValueError) as exc:
            problems.append("%s: does not parse (%s)" % (rel, exc))
            continue
        for module, line, raw in imported_names(tree):
            checked += 1
            modules_seen.add(module)
            if module in FORBIDDEN:
                problems.append("%s:%d: network module is forbidden: %s"
                                % (rel, line, raw))
            elif module in ALLOWED or module in local:
                continue
            else:
                problems.append("%s:%d: module is outside the frozen stdlib "
                                "allowlist: %s" % (rel, line, raw))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "__import__":
                dynamic.append("%s:%d: __import__() is a dynamic import path"
                               % (rel, node.lineno))
    problems.extend(dynamic)
    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("check-stdlib-imports: PASS")
    print("  python files: %d" % len(files))
    print("  import statements checked: %d" % checked)
    print("  modules seen: %s" % ", ".join(sorted(modules_seen)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
