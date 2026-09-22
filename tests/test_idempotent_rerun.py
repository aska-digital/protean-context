#!/usr/bin/env python3
"""Step 10: rerunning `init` with the same arguments changes zero bytes.

Locked semantics (decision D5.2): `init` is ensure-exist per file, so a second
run with the same arguments classifies every planned file as `unchanged`,
performs zero writes, and exits 0. Registry entries are appended only for names
that are not present yet.

The test proves that at the byte level rather than from the summary line: the
per-file sha256 map, the receipt text, and every file's mtime are identical
before and after the second run, and the second run prints no write line.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pc_support

REGISTRY = "eldunarya/eldunarya.json"
ROUTER = "eldunarya/eldunari/demo/ROUTER.md"
SECOND_ROUTER = "eldunarya/eldunari/second/ROUTER.md"


def receipt_text(target):
    return pc_support.read_text(os.path.join(target, pc_support.RECEIPT))


class TestIdempotentRerun(unittest.TestCase):
    def test_second_init_writes_nothing_and_changes_no_bytes(self):
        with tempfile.TemporaryDirectory(prefix="idempotent-rerun-") as work:
            target = os.path.join(work, "created")
            first = pc_support.run_cli("init", "--target", target, "--name", "demo")
            self.assertEqual(0, first.returncode, first.stderr)

            before_files = pc_support.file_map(target)
            before_mtimes = pc_support.mtimes(target)
            before_receipt = receipt_text(target)
            self.assertIn(ROUTER, before_files)
            self.assertIn(pc_support.RECEIPT, before_files)

            second = pc_support.run_cli("init", "--target", target, "--name", "demo")
            self.assertEqual(0, second.returncode, second.stderr)

            self.assertEqual(before_files, pc_support.file_map(target),
                             "a rerun must not change a single file byte")
            self.assertEqual(before_mtimes, pc_support.mtimes(target),
                             "a rerun must not rewrite or touch any file (the "
                             "receipt included)")
            self.assertEqual(before_receipt, receipt_text(target),
                             "the receipt must be byte-stable across a rerun")
            self.assertNotIn("wrote:", second.stdout,
                             "a rerun must print no write line:\n%s" % second.stdout)
            self.assertNotIn("backup:", second.stdout)
            self.assertIn("unchanged: %s" % REGISTRY, second.stdout)
            self.assertIn("unchanged: %s" % ROUTER, second.stdout)
            self.assertIn("summary: create=0 replace=0 unchanged=", second.stdout)
            self.assertIn("conflict=0", second.stdout)
            self.assertIn("result: ok", second.stdout)

    def test_plan_agrees_with_init_and_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="idempotent-rerun-") as work:
            target = os.path.join(work, "created")
            self.assertEqual(0, pc_support.run_cli(
                "init", "--target", target, "--name", "demo").returncode)
            before = pc_support.file_map(target)
            before_mtimes = pc_support.mtimes(target)

            planned = pc_support.run_cli("plan", "--target", target, "--name", "demo")
            self.assertEqual(0, planned.returncode, planned.stderr)
            self.assertEqual(before, pc_support.file_map(target),
                             "plan must write nothing on an initialized target")
            self.assertEqual(before_mtimes, pc_support.mtimes(target),
                             "plan must not touch any file")
            self.assertIn("result: dry-run, no files written", planned.stdout)
            self.assertIn("would unchanged: %s" % REGISTRY, planned.stdout)

    def test_adding_a_name_creates_only_that_tree(self):
        with tempfile.TemporaryDirectory(prefix="idempotent-rerun-") as work:
            target = os.path.join(work, "created")
            self.assertEqual(0, pc_support.run_cli(
                "init", "--target", target, "--name", "demo").returncode)
            before = pc_support.file_map(target)
            router_sha = before[ROUTER]
            router_mtime = pc_support.mtimes(target)[ROUTER]

            grown = pc_support.run_cli("init", "--target", target,
                                       "--name", "demo", "--name", "second")
            self.assertEqual(0, grown.returncode, grown.stderr)
            after = pc_support.file_map(target)
            self.assertIn(SECOND_ROUTER, after,
                          "the added name must get its own ROUTER.md")
            self.assertEqual(router_sha, after[ROUTER],
                             "the existing Eldunari must not be rewritten")
            self.assertEqual(router_mtime, pc_support.mtimes(target)[ROUTER],
                             "the existing Eldunari's ROUTER.md must not be touched")
            self.assertIn('"second"', pc_support.read_text(
                os.path.join(target, REGISTRY)),
                "a new name must be appended to the registry")

    def test_duplicate_name_in_one_call_is_a_no_op(self):
        with tempfile.TemporaryDirectory(prefix="idempotent-rerun-") as work:
            target = os.path.join(work, "created")
            result = pc_support.run_cli("init", "--target", target,
                                        "--name", "demo", "--name", "demo")
            self.assertEqual(0, result.returncode, result.stderr)
            registry = pc_support.read_text(os.path.join(target, REGISTRY))
            self.assertEqual(1, registry.count('"name": "demo"'),
                             "a repeated --name must be recorded once")

    def test_third_run_after_a_growth_run_is_stable_again(self):
        with tempfile.TemporaryDirectory(prefix="idempotent-rerun-") as work:
            target = os.path.join(work, "created")
            names = ["demo", "second"]
            args = []
            for name in names:
                args += ["--name", name]
            self.assertEqual(0, pc_support.run_cli("init", "--target", target,
                                                   *args).returncode)
            before_files = pc_support.file_map(target)
            before_mtimes = pc_support.mtimes(target)
            again = pc_support.run_cli("init", "--target", target, *args)
            self.assertEqual(0, again.returncode, again.stderr)
            self.assertEqual(before_files, pc_support.file_map(target))
            self.assertEqual(before_mtimes, pc_support.mtimes(target))


if __name__ == "__main__":
    unittest.main()
