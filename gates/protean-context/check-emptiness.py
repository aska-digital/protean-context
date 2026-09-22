#!/usr/bin/env python3
"""check-emptiness.py - gate 3 of build/verify-all.py.

Proves that no content is bundled anywhere:

  * the shipped template tree contains only allowlisted files (templates, schema
    documents, documentation, and `.gitkeep`-class markers);
  * `eldunarya/eldunari/` ships with no named Eldunari at all;
  * `arif/records/`, `arif/content/`, and `arif/index/` ship with markers only;
  * the shipped `arif.json` has `embedding.enabled` false;
  * a real `init` into a temporary target creates exactly the documented files
    and leaves `records/`, `content/`, and `index/` empty.

Usage: python3 gates/protean-context/check-emptiness.py [repo-root]
Exit: 0 pass; 1 violation; 2 missing source data.
"""

import json
import os
import subprocess
import sys
import tempfile

GATE = "check-emptiness.py"
TEMPLATES = "templates/protean-context"
SHIPPED_ALLOWLIST = (
    "eldunarya/eldunarya.json",
    "eldunarya/eldunari/ROUTER.template.md",
    "eldunarya/eldunari/modules/README.template.md",
    "arif/arif.json",
    "arif/adapters/README.md",
    "arif/records/.gitkeep",
    "arif/content/.gitkeep",
    "arif/index/.gitkeep",
    "schema/eldunarya.schema.json",
    "schema/eldunari.schema.json",
    "schema/arif-store.schema.json",
    "schema/arif-record.schema.json",
    "docs/rehoming.md",
)
CREATED_ALLOWLIST = (
    ".protean-context-receipt.json",
    "arif/adapters/README.md",
    "arif/arif.json",
    "eldunarya/eldunari/demo/ROUTER.md",
    "eldunarya/eldunari/demo/modules/README.md",
    "eldunarya/eldunarya.json",
)
ALWAYS_EMPTY = ("arif/records", "arif/content", "arif/index")


def relative_files(root):
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            found.append(os.path.relpath(os.path.join(base, name), root))
    return sorted(found)


def marker_only(root, rel):
    path = os.path.join(root, rel)
    if not os.path.isdir(path):
        return ["%s: missing directory" % rel]
    entries = os.listdir(path)
    if any(not name.startswith(".") for name in entries):
        return ["%s: holds bundled content: %s"
                % (rel, sorted(n for n in entries if not n.startswith(".")))]
    return []


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    templates = os.path.join(root, TEMPLATES)
    bootstrap = os.path.join(root, "scripts", "protean-context", "bootstrap.py")
    for path in (templates, bootstrap):
        if not os.path.exists(path):
            sys.stderr.write("MISSING: %s\n" % os.path.relpath(path, root))
            return 2

    problems = []
    shipped = relative_files(templates)
    for rel in shipped:
        if rel not in SHIPPED_ALLOWLIST:
            problems.append("%s: file is not on the emptiness allowlist" % rel)
    for rel in SHIPPED_ALLOWLIST:
        if rel not in shipped:
            problems.append("%s: allowlisted file is missing" % rel)
    for rel in ALWAYS_EMPTY:
        problems.extend(marker_only(templates, rel))
    eldunari_home = os.path.join(templates, "eldunarya", "eldunari")
    for name in sorted(os.listdir(eldunari_home)) if os.path.isdir(eldunari_home) else []:
        path = os.path.join(eldunari_home, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "ROUTER.md")):
            problems.append("eldunarya/eldunari/%s: a named Eldunari ships here" % name)

    manifest_path = os.path.join(templates, "arif", "arif.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if (manifest.get("embedding") or {}).get("enabled") is not False:
            problems.append("arif/arif.json: embedding.enabled is not false at ship")
    except (ValueError, OSError) as exc:
        problems.append("arif/arif.json: unreadable (%s)" % exc)

    problems.extend(check_created_tree(root, bootstrap))

    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("check-emptiness: PASS")
    print("  shipped template files: %d" % len(shipped))
    print("  created tree: exactly %d files, records/content/index empty"
          % len(CREATED_ALLOWLIST))
    return 0


def check_created_tree(root, bootstrap):
    problems = []
    with tempfile.TemporaryDirectory(prefix="check-emptiness-") as work:
        target = os.path.join(work, "target")
        result = subprocess.run(
            [sys.executable, bootstrap, "init", "--target", target, "--name", "demo"],
            capture_output=True, text=True, cwd=root, timeout=120)
        if result.returncode != 0:
            problems.append("init failed (%s): %s"
                            % (result.returncode, result.stderr.strip()[:200]))
            return problems
        created = relative_files(target)
        for rel in created:
            if rel not in CREATED_ALLOWLIST:
                problems.append("created %s: file is not on the allowlist" % rel)
        for rel in CREATED_ALLOWLIST:
            if rel not in created:
                problems.append("created %s: expected file is missing" % rel)
        for rel in ALWAYS_EMPTY:
            path = os.path.join(target, rel)
            if not os.path.isdir(path):
                problems.append("created %s: missing directory" % rel)
            elif os.listdir(path):
                problems.append("created %s: not empty: %s"
                                % (rel, sorted(os.listdir(path))))
    return problems


if __name__ == "__main__":
    sys.exit(main(sys.argv))
