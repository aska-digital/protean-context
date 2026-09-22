#!/usr/bin/env python3
"""check-identifiers.py - gate 6 of build/verify-all.py.

Proves that no internal identity term appears in this public tree, and that the
one documented allowlist is explicit rather than silent:

  * the blocklist is read from build/identifiers.yaml (this repository's own
    term registry), so no codename is spelled in this script;
  * a hit anywhere else in the tree is a failure, named with its surface and
    line number - there is no baseline to grandfather anything;
  * the allowlisted public system terms (eldunari, eldunarya, arif) are listed
    with a reason and cite architecture decision D3.1 of the protean-context
    lock (2026-09-22);
  * no separate baseline file exists, because a silent baseline is forbidden.

Usage: python3 gates/protean-context/check-identifiers.py [repo-root]
Exit: 0 pass; 1 leak found; 2 missing source data.
"""

import os
import re
import sys

GATE = "check-identifiers.py"
REGISTRY = "build/identifiers.yaml"
BASELINE_NAMES = ("build/internal-names-baseline.yaml",
                  "build/identifiers-baseline.yaml")
SKIP_DIRS = (".git", "__pycache__", ".protean-backup")
BINARY_EXT = (".pyc", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".woff",
              ".woff2", ".ttf", ".ico")
REQUIRED_TERMS = ("eldunari", "eldunarya", "arif")
CITATION = "architecture decision D3.1 of the protean-context lock (2026-09-22)"


def parse_registry(text):
    """Read the blocklist and the documented allowlist out of the registry."""
    blocklist = []
    terms = []
    baseline = []
    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("internal_agent_names:"):
            section = "blocklist"
            continue
        if stripped.startswith("public_system_terms:"):
            section = "terms"
            continue
        if stripped.startswith("baseline:"):
            section = "baseline"
            inline = stripped.split(":", 1)[1].strip()
            if inline not in ("[]", ""):
                baseline.append(inline)
            continue
        if section == "blocklist" and stripped.startswith("- "):
            blocklist.append(stripped[2:].strip().strip('"\''))
            continue
        if section == "terms" and stripped.startswith("- term:"):
            terms.append(stripped.split(":", 1)[1].strip().strip('"\''))
            continue
        if section == "baseline" and stripped.startswith("- "):
            baseline.append(stripped[2:].strip())
    return blocklist, terms, baseline


def scan(root, patterns):
    hits = []
    scanned = 0
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root)
            if rel == REGISTRY or os.path.basename(rel) == GATE:
                continue
            if rel.endswith(BINARY_EXT):
                continue
            try:
                with open(full, "r", encoding="utf-8") as handle:
                    lines = handle.read().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            scanned += 1
            for number, line in enumerate(lines, 1):
                for name_, pattern in patterns:
                    if pattern.search(line):
                        hits.append((rel, number, name_))
    return hits, scanned


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    registry_path = os.path.join(root, REGISTRY)
    if not os.path.isfile(registry_path):
        sys.stderr.write("MISSING: %s\n" % REGISTRY)
        return 2
    with open(registry_path, "r", encoding="utf-8") as handle:
        text = handle.read()
    blocklist, terms, baseline = parse_registry(text)
    problems = []
    if not blocklist:
        sys.stderr.write("MISSING: %s lists no internal agent names\n" % REGISTRY)
        return 2
    if sorted(terms) != sorted(REQUIRED_TERMS):
        problems.append("%s: public_system_terms is %s, expected %s"
                        % (REGISTRY, sorted(terms), sorted(REQUIRED_TERMS)))
    if CITATION not in text:
        problems.append("%s: the allowlist does not cite the decision record (%s)"
                        % (REGISTRY, CITATION))
    if baseline:
        problems.append("%s: a baseline entry exists (%s); a silent baseline is "
                        "forbidden" % (REGISTRY, baseline))
    for name in BASELINE_NAMES:
        if os.path.isfile(os.path.join(root, name)):
            problems.append("%s: baseline file exists; this gate has no baseline"
                            % name)

    patterns = [(name, re.compile(re.escape(name), re.IGNORECASE))
                for name in blocklist if name]
    hits, scanned = scan(root, patterns)
    for rel, number, name in hits:
        problems.append("%s:%d: internal identity term found (%s)" % (rel, number, name))

    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("check-identifiers: PASS")
    print("  files scanned: %d" % scanned)
    print("  blocklist terms: %d" % len(blocklist))
    print("  allowlisted public system terms: %s" % ", ".join(REQUIRED_TERMS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
