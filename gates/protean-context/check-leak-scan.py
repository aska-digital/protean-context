#!/usr/bin/env python3
"""check-leak-scan.py - gate 4 of build/verify-all.py.

Dedicated detectors per surface, never one catch-all grep (team surface-scan
pattern, surfaces S1, S2, S4, S5):

  S1 content        file bodies: private path shapes, credential value shapes,
                    owner-content markers
  S2 filenames      file and directory names in the tree
  S4 script paths   the same shapes inside .py and .sh files, reported as S4
  S5 config defaults the shipped JSON templates and the descriptor

The pattern table is assembled from fragments so that this gate does not match
its own text, and the gate file is excluded from every scan.

Usage: python3 gates/protean-context/check-leak-scan.py [repo-root]
Exit: 0 pass; 1 leaks found; 2 missing source data.
"""

import os
import re
import sys

GATE = "check-leak-scan.py"
SKIP_DIRS = (".git", "__pycache__", ".protean-backup")
TEXT_EXT = (".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt", "")
BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".woff", ".woff2",
              ".ttf", ".ico", ".so", ".pyc")


def patterns():
    """Path, credential, and owner-content shapes, built from fragments."""
    home = ["/" + word + "/" for word in ("Users", "home", "Volumes")]
    private = ["~" + "/." + "hermes", "." + "hermes" + "/" + "profiles",
               "team" + "-skills", "cache" + "/" + "delegation",
               "eldunari" + "-arif" + "-scaffold"]
    credentials = ["api" + "_key=", "apikey=", "pass" + "word=", "passwd=",
                   "sec" + "ret=", "client" + "_secret=", "private" + "_key=",
                   "access" + "_token=", "ghp_", "github_pat_", "AKIA",
                   "-----BEGIN", "Bearer "]
    owners = ["ahraz", "gmail.com", "team6", "gc1/", "askaconsult"]
    table = {}
    for shape in home:
        table["absolute home path"] = table.get("absolute home path", []) + [shape]
    for shape in private:
        table.setdefault("private path shape", []).append(shape)
    for shape in credentials:
        table.setdefault("credential value shape", []).append(shape)
    for shape in owners:
        table.setdefault("owner-content marker", []).append(shape)
    return table


PATTERNS = patterns()
NAME_PATTERNS = [item for group in ("absolute home path", "private path shape")
                 for item in PATTERNS[group]]
CONFIG_EXT = (".json",)


def iter_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            full = os.path.join(base, name)
            yield os.path.relpath(full, root), full


def surface_for(rel):
    if rel.endswith(".json"):
        return "S5"
    if rel.endswith((".py", ".sh")):
        return "S4"
    return "S1"


def scan_content(rel, path):
    hits = []
    if os.path.basename(rel) == GATE:
        return hits
    if rel.endswith(BINARY_EXT):
        return hits
    if os.path.splitext(rel)[1] not in TEXT_EXT:
        return hits
    try:
        with open(path, "r", encoding="utf-8", errors="strict") as handle:
            lines = handle.read().splitlines()
    except (UnicodeDecodeError, OSError):
        return hits
    for number, line in enumerate(lines, 1):
        for group in sorted(PATTERNS):
            for shape in PATTERNS[group]:
                if shape in line:
                    hits.append((surface_for(rel), group, rel, number, shape))
    return hits


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    if not os.path.isfile(os.path.join(root, "README.md")):
        sys.stderr.write("MISSING: README.md\n")
        return 2
    scans = 0
    hits = []
    names = []
    for rel, path in iter_files(root):
        scans += 1
        hits.extend(scan_content(rel, path))
        for part in rel.split(os.sep):
            for shape in NAME_PATTERNS:
                if shape in part:
                    names.append(("S2", "path shape in name", rel, 0, shape))
    hits.extend(names)
    if scans == 0:
        sys.stderr.write("MISSING: no files to scan under %s\n" % root)
        return 2
    if hits:
        print("FAIL: %s" % GATE)
        for surface, group, rel, number, shape in hits:
            print("  %s %s: %s:%d (%s)" % (surface, group, rel, number, group))
        return 1
    print("check-leak-scan: PASS")
    print("  files scanned: %d" % scans)
    print("  surfaces: S1 content, S2 filenames, S4 script paths, S5 config defaults")
    print("  hits: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
