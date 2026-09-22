#!/usr/bin/env python3
"""check-post-install.py - the composer's post-install gate for this ingredient.

The composer runs this with `cwd` set to the install target, after staging the
four install targets and before promoting them:

    python3 gates/protean-context/check-post-install.py .

It asserts:

  * each of the four install targets is present under the given root and holds
    files (a staged-but-empty target is a failure, not a pass);
  * every contract carrier found in the installed tree agrees byte for byte
    with the contract line this gate carries;
  * at least one carrier is present, so the check can never pass vacuously.

The contract line below is the published sentence (architecture decision D2 of
the protean-context lock (2026-09-22)); gate 1 keeps it byte-identical to
README.md line 1, to the descriptor's `contract`, and to the skill carrier, so
drift in any one of them fails this repository's own gate run first.

Usage: python3 gates/protean-context/check-post-install.py [install-root]
Exit: 0 pass; 1 violation; 2 missing source data (no install root, no carrier).
"""

import json
import os
import re
import sys

GATE = "check-post-install.py"
INSTALL_TARGETS = ("skills/protean-context", "scripts/protean-context",
                   "templates/protean-context", "gates/protean-context")
CONTRACT_LINE = "Versioned empty scaffolds and a stdlib-only bootstrap CLI that initialize a user-owned Eldunarya knowledge tree and Arif knowledge base with no bundled data."
SKILL = "skills/protean-context/SKILL.md"
DESCRIPTOR = "protean-ingredient.json"
DESCRIPTION_RE = re.compile(r'^description:\s*(.+?)\s*$', re.MULTILINE)


def read_first_line(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.readline().rstrip("\n")


def carriers(root):
    """Contract carriers present in the installed tree, as (label, value)."""
    found = []
    readme = os.path.join(root, "README.md")
    if os.path.isfile(readme):
        found.append(("README.md line 1", read_first_line(readme)))
    descriptor = os.path.join(root, DESCRIPTOR)
    if os.path.isfile(descriptor):
        try:
            with open(descriptor, "r", encoding="utf-8") as handle:
                document = json.load(handle)
            found.append((DESCRIPTOR + " contract", document.get("contract")))
        except ValueError:
            found.append((DESCRIPTOR + " contract", "<unparseable>"))
    skill = os.path.join(root, SKILL)
    if os.path.isfile(skill):
        with open(skill, "r", encoding="utf-8") as handle:
            match = DESCRIPTION_RE.search(handle.read())
        if match:
            found.append((SKILL + " description", match.group(1)))
    return found


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    if not os.path.isdir(root):
        sys.stderr.write("MISSING: install root %s\n" % root)
        return 2
    problems = []
    for rel in INSTALL_TARGETS:
        path = os.path.join(root, rel)
        if not os.path.isdir(path):
            problems.append("install target is missing: %s" % rel)
            continue
        if not any(os.path.isfile(os.path.join(base, name))
                   for base, _dirs, files in os.walk(path) for name in files):
            problems.append("install target holds no files: %s" % rel)
    found = carriers(root)
    if not found:
        sys.stderr.write("MISSING: no contract carrier installed under %s\n" % root)
        return 2
    for label, value in found:
        if value != CONTRACT_LINE:
            problems.append("%s: does not carry the contract line byte for byte"
                            % label)
    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("check-post-install: PASS")
    print("  install targets present: %d" % len(INSTALL_TARGETS))
    print("  contract carriers checked: %d" % len(found))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
