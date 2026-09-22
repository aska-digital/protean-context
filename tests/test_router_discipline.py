#!/usr/bin/env python3
"""Step 14: router discipline over initialized targets.

Locked semantics (zero-context slice): an initialized target passes when
every unfenced `modules/<file>.md -> description` pointer line in each
Eldunari's ROUTER.md resolves to a regular file under that Eldunari's
modules/, module-body pointers resolve the same way, and no markdown
module stands without an unfenced router pointer naming it. Fenced code
blocks are ignored, zero pointers is a pass, and a missing ROUTER.md is
a failure, never a pass. The check writes nothing.

Positive: P1 fresh init verifies clean; P2 init plus one module plus one
pointer verifies clean. Red teeth: R1 unresolved, R2 homeless, R3
nonconforming, R4 missing router each fail with the named problem class.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pc_support

ROUTER = "eldunarya/eldunari/demo/ROUTER.md"
MODULES = "eldunarya/eldunari/demo/modules"


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def append(path, text):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def initialize(work, name="demo"):
    target = os.path.join(work, "created")
    result = pc_support.run_cli("init", "--target", target, "--name", name)
    if result.returncode != 0:
        raise AssertionError("init failed (%d): %s" % (result.returncode,
                                                       result.stderr))
    return target


def verify(target):
    return pc_support.run_cli("verify", "--target", target)


class TestRouterDiscipline(unittest.TestCase):
    def test_p1_fresh_init_verifies_clean(self):
        with tempfile.TemporaryDirectory(prefix="router-discipline-") as work:
            target = initialize(work)
            before = pc_support.file_map(target)
            result = verify(target)
            self.assertEqual(0, result.returncode,
                             result.stdout + result.stderr)
            self.assertIn("check router-discipline: ok", result.stdout)
            self.assertIn("result: ok", result.stdout)
            self.assertEqual(before, pc_support.file_map(target),
                             "verify must remain read-only")

    def test_p2_module_plus_pointer_verifies_clean(self):
        with tempfile.TemporaryDirectory(prefix="router-discipline-") as work:
            target = initialize(work)
            write(os.path.join(target, MODULES, "fact.md"),
                  "the demo fact: synthetic\n")
            append(os.path.join(target, ROUTER),
                   "modules/fact.md -> the demo fact\n")
            result = verify(target)
            self.assertEqual(0, result.returncode,
                             result.stdout + result.stderr)
            self.assertIn("check router-discipline: ok", result.stdout)

    def test_r1_unresolved_pointer_fails(self):
        with tempfile.TemporaryDirectory(prefix="router-discipline-") as work:
            target = initialize(work)
            append(os.path.join(target, ROUTER),
                   "modules/ghost.md -> missing\n")
            result = verify(target)
            self.assertEqual(6, result.returncode,
                             result.stdout + result.stderr)
            self.assertIn("unresolved", result.stdout)

    def test_r2_homeless_module_fails(self):
        with tempfile.TemporaryDirectory(prefix="router-discipline-") as work:
            target = initialize(work)
            write(os.path.join(target, MODULES, "orphan.md"),
                  "a home with no pointer: synthetic\n")
            result = verify(target)
            self.assertEqual(6, result.returncode,
                             result.stdout + result.stderr)
            self.assertIn("homeless", result.stdout)

    def test_r3_nonconforming_pointer_fails(self):
        with tempfile.TemporaryDirectory(prefix="router-discipline-") as work:
            target = initialize(work)
            append(os.path.join(target, ROUTER),
                   "modules/nested/thing.md -> x\n")
            result = verify(target)
            self.assertEqual(6, result.returncode,
                             result.stdout + result.stderr)
            self.assertIn("nonconforming", result.stdout)

    def test_r4_missing_router_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="router-discipline-") as work:
            target = initialize(work)
            os.remove(os.path.join(target, ROUTER))
            result = verify(target)
            self.assertEqual(6, result.returncode,
                             result.stdout + result.stderr)
            self.assertIn("problem:", result.stdout)


if __name__ == "__main__":
    unittest.main()
