#!/usr/bin/env python3
"""
verify-all.py - the deterministic gate runner of the protean-context scaffold.

Runs the repository's public gates in documented order. Every step runs as a
subprocess with a 300 second timeout, and the runner is fail closed: it exits 0
only when every step exits 0. A gate that exits 2 reports `MISSING: <path>` on
stderr; the runner prints `SKIPPED: missing <path>` and counts that step as NOT
PASS, so a skip can never produce a green run.

ORDER (this list is the gate list, and this docstring is authoritative):

  1.  contract line and descriptor parity            gates/protean-context/check-manifest-parity.py
  2.  every shipped JSON, the four schemas, ingest   gates/protean-context/check-schema.py
  3.  no bundled content, empty created trees        gates/protean-context/check-emptiness.py
  4.  privacy scan across four surfaces              gates/protean-context/check-leak-scan.py
  5.  token and default-path discipline              gates/protean-context/check-path-portability.py
  6.  no internal identity terms                     gates/protean-context/check-identifiers.py
  7.  stdlib-only imports, proven by AST             gates/protean-context/check-stdlib-imports.py
  8.  synthetic fixtures only                        gates/protean-context/check-synthetic-fixtures.py
  9.  no live-state reads, write confinement         python3 -m unittest tests.test_no_live_state
  10. rerunning init changes zero bytes              python3 -m unittest tests.test_idempotent_rerun
  11. two independent inits are identical           python3 -m unittest tests.test_deterministic_init
  12. remove deletes only what init created          python3 -m unittest tests.test_removal
  13. forward-only, additive, backed-up migrations   python3 -m unittest tests.test_migration_rules
  14. fresh-user install, plan, init, verify         gates/protean-context/fresh-install-test.py

Exit: 0 = all 14 steps pass; 1 = any step failed or skipped.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TIMEOUT = 300

STEPS = (
    ("contract and descriptor parity",
     [sys.executable, "gates/protean-context/check-manifest-parity.py"]),
    ("shipped JSON, schemas, ingest", 
     [sys.executable, "gates/protean-context/check-schema.py"]),
    ("no bundled content",
     [sys.executable, "gates/protean-context/check-emptiness.py"]),
    ("privacy scan",
     [sys.executable, "gates/protean-context/check-leak-scan.py"]),
    ("path portability",
     [sys.executable, "gates/protean-context/check-path-portability.py"]),
    ("identifiers",
     [sys.executable, "gates/protean-context/check-identifiers.py"]),
    ("stdlib-only imports",
     [sys.executable, "gates/protean-context/check-stdlib-imports.py"]),
    ("synthetic fixtures",
     [sys.executable, "gates/protean-context/check-synthetic-fixtures.py"]),
    ("no live state (unit test)",
     [sys.executable, "-m", "unittest", "tests.test_no_live_state"]),
    ("idempotent rerun (unit test)",
     [sys.executable, "-m", "unittest", "tests.test_idempotent_rerun"]),
    ("deterministic init (unit test)",
     [sys.executable, "-m", "unittest", "tests.test_deterministic_init"]),
    ("removal (unit test)",
     [sys.executable, "-m", "unittest", "tests.test_removal"]),
    ("migration rules (unit test)",
     [sys.executable, "-m", "unittest", "tests.test_migration_rules"]),
    ("fresh install end to end",
     [sys.executable, "gates/protean-context/fresh-install-test.py"]),
)


def missing_source(stderr):
    for line in (stderr or "").splitlines():
        if line.startswith("MISSING: "):
            return line[len("MISSING: "):].strip()
    return None


def run_step(index, name, command):
    print("=" * 72)
    print("STEP %d/%d: %s" % (index, len(STEPS), name))
    print("=" * 72)
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        print("NOT PASS: %s (timeout after %ds)" % (name, TIMEOUT))
        return "NOT PASS"
    except OSError as exc:
        print("NOT PASS: %s (could not run: %s)" % (name, exc))
        return "NOT PASS"
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode == 2:
        print("SKIPPED: missing %s" % (missing_source(result.stderr) or name))
        if result.stderr:
            print(result.stderr.rstrip())
        return "SKIPPED (NOT PASS)"
    if result.returncode != 0:
        print("NOT PASS: %s (exit %d)" % (name, result.returncode))
        if result.stderr:
            print(result.stderr.rstrip())
        return "NOT PASS"
    print("PASS: %s" % name)
    return "PASS"


def main(argv):
    if len(argv) > 1:
        sys.stderr.write("usage: python3 build/verify-all.py\n")
        return 2
    print("protean-context gate runner")
    print("root: %s" % ROOT)
    print("steps: %d, timeout per step: %ds" % (len(STEPS), TIMEOUT))
    results = []
    for index, (name, command) in enumerate(STEPS, 1):
        results.append((index, name, run_step(index, name, command)))
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    passed = sum(1 for _i, _n, status in results if status == "PASS")
    skipped = sum(1 for _i, _n, status in results if status.startswith("SKIPPED"))
    failed = len(results) - passed - skipped
    for index, name, status in results:
        print("  %2d %-9s %s" % (index, status, name))
    print("  steps=%d pass=%d not-pass=%d skipped=%d" % (len(results), passed,
                                                         failed, skipped))
    if passed == len(results):
        print("RESULT: all %d steps PASS" % len(results))
        return 0
    print("RESULT: NOT GREEN (a skip is not a pass)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
