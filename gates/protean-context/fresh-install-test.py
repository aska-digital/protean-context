#!/usr/bin/env python3
"""fresh-install-test.py - gate 14 of build/verify-all.py.

The fresh-user proof:

  1. take a copy of HEAD (a detached git worktree, so the run is against the
     committed tree and not against local edits);
  2. run `bash install.sh --target <tmp>` from that copy and read back the four
     install targets it printed;
  3. run `plan`, `init`, and `verify` from the installed copy, offline, and
     require exit 0 from each;
  4. run gate 3 against the installed copy (its templates create an empty tree)
     and gate 2 against the worktree (shipped templates plus synthetic fixtures
     satisfy the schema rules);
  5. prove the absence of any plugin or MCP surface by read-back.

Usage: python3 gates/protean-context/fresh-install-test.py [repo-root]
Exit: 0 pass; 1 a step failed; 2 missing source data (no HEAD to copy).
"""

import os
import subprocess
import sys
import tempfile

GATE = "fresh-install-test.py"
INSTALL_TARGETS = ("skills/protean-context", "scripts/protean-context",
                   "templates/protean-context", "gates/protean-context")


def run(command, cwd, timeout=300):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def step(name, command, cwd, problems):
    result = run(command, cwd)
    print("  step: %s -> exit %d" % (name, result.returncode))
    if result.returncode != 0:
        problems.append("%s failed (%d): %s" % (name, result.returncode,
                                                (result.stderr or "").strip()[:300]))
        if result.stdout:
            print(result.stdout.rstrip())
    return result


def main(argv):
    root = os.path.abspath(argv[1] if len(argv) > 1 else ".")
    installer = os.path.join(root, "install.sh")
    if not os.path.isfile(installer):
        sys.stderr.write("MISSING: install.sh\n")
        return 2
    probe = run(["git", "-C", root, "rev-parse", "--verify", "HEAD"], root)
    if probe.returncode != 0:
        sys.stderr.write("MISSING: no HEAD commit to copy in %s\n" % root)
        return 2

    problems = []
    print("fresh-install-test: %s" % root)
    with tempfile.TemporaryDirectory(prefix="fresh-install-") as work:
        head = os.path.join(work, "head")
        added = run(["git", "-C", root, "worktree", "add", "--detach", head, "HEAD"],
                    root)
        if added.returncode != 0:
            sys.stderr.write("MISSING: cannot create a worktree at HEAD (%s)\n"
                             % (added.stderr or "").strip()[:200])
            return 2
        try:
            target = os.path.join(work, "installed")
            result = step("install.sh --target (dry-run)",
                          ["bash", "install.sh", "--target",
                           os.path.join(work, "dry"), "--dry-run"], head, problems)
            if "no files written" not in result.stdout:
                problems.append("install.sh --dry-run did not report that it wrote "
                                "nothing")
            if os.path.exists(os.path.join(work, "dry")):
                problems.append("install.sh --dry-run created its target directory")
            result = step("install.sh --target", ["bash", "install.sh", "--target",
                                                  target], head, problems)
            if "wrote: " not in result.stdout:
                problems.append("install.sh did not print the paths it wrote")
            for rel in INSTALL_TARGETS:
                if not os.path.exists(os.path.join(target, rel)):
                    problems.append("install target is missing after install: %s" % rel)

            bootstrap = os.path.join(target, "scripts", "protean-context",
                                     "bootstrap.py")
            scratch = os.path.join(work, "created")
            for name, extra in (("plan", ["--name", "demo"]),
                                ("init", ["--name", "demo"]),
                                ("verify", [])):
                command = [sys.executable, bootstrap, name, "--target", scratch,
                           "--offline"] + extra
                step("installed bootstrap.py %s" % name, command, target, problems)

            gate3 = os.path.join(target, "gates", "protean-context",
                                 "check-emptiness.py")
            if os.path.isfile(gate3):
                step("check-emptiness.py against the installed copy",
                     [sys.executable, gate3, target], work, problems)
            else:
                problems.append("installed gate script is missing: check-emptiness.py")
            gate2 = os.path.join(head, "gates", "protean-context", "check-schema.py")
            if os.path.isfile(gate2):
                step("check-schema.py against the committed tree",
                     [sys.executable, gate2, head], work, problems)
            else:
                problems.append("gate script is missing in the worktree: "
                                "check-schema.py")

            forbidden = []
            for base, dirs, files in os.walk(target):
                for name in files:
                    if name in ("plugin.js", "mcp.json"):
                        forbidden.append(os.path.relpath(os.path.join(base, name),
                                                         target))
            if forbidden:
                problems.append("plugin or MCP surface present: %s" % forbidden)
        finally:
            run(["git", "-C", root, "worktree", "remove", "--force", head], root)

    if problems:
        print("FAIL: %s" % GATE)
        for problem in problems:
            print("  " + problem)
        return 1
    print("fresh-install-test: PASS")
    print("  installed targets: %d" % len(INSTALL_TARGETS))
    print("  plan, init, verify: exit 0 offline")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
