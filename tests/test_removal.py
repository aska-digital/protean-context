#!/usr/bin/env python3
"""Step 12: `remove` deletes only what `init` created, and only while unmodified.

Locked semantics (decision D5.4): the init receipt lists every path init created
with its sha256; `remove` deletes exactly those paths whose current hash still
matches, skips and reports a path whose hash differs (the user modified it),
never touches an unlisted file, removes a directory only when it is empty, and
deletes the receipt last. `remove --dry-run` prints the same plan and deletes
nothing.

Canaries here are the two classes of file that must survive: a user-modified
file that the receipt lists, and a user file the receipt has never heard of.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pc_support

ROUTER = "eldunarya/eldunari/demo/ROUTER.md"
MODULES_README = "eldunarya/eldunari/demo/modules/README.md"
REGISTRY = "eldunarya/eldunarya.json"
ARIF_MANIFEST = "arif/arif.json"
ADAPTERS_README = "arif/adapters/README.md"
RECEIPTED_FILES = (REGISTRY, ROUTER, MODULES_README, ARIF_MANIFEST, ADAPTERS_README)
ROOT_CANARY = "CANARY.txt"
ARIF_CANARY = "arif/user-notes.txt"
MODULES_CANARY = "eldunarya/eldunari/demo/modules/user-note.md"
USER_EDIT = "user edit: this line is not scaffold content\n"


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def initialize(work, name="demo"):
    target = os.path.join(work, "created")
    result = pc_support.run_cli("init", "--target", target, "--name", name)
    if result.returncode != 0:
        raise AssertionError("init failed (%d): %s" % (result.returncode,
                                                       result.stderr))
    return target


class TestRemoval(unittest.TestCase):
    def test_remove_deletes_only_unmodified_receipted_paths(self):
        with tempfile.TemporaryDirectory(prefix="removal-mixed-") as work:
            target = initialize(work)
            write(os.path.join(target, ROUTER), USER_EDIT)
            write(os.path.join(target, ROOT_CANARY), "keep me\n")
            write(os.path.join(target, ARIF_CANARY), "keep me too\n")

            result = pc_support.run_cli("remove", "--target", target)
            self.assertEqual(0, result.returncode, result.stderr)

            self.assertTrue(os.path.isfile(os.path.join(target, ROUTER)),
                            "a user-modified receipted file must survive")
            self.assertEqual(USER_EDIT,
                             pc_support.read_text(os.path.join(target, ROUTER)))
            self.assertIn("skipped: %s (user-modified)" % ROUTER, result.stdout)

            for rel in (ROOT_CANARY, ARIF_CANARY):
                self.assertTrue(os.path.isfile(os.path.join(target, rel)),
                                "an unlisted file must never be touched: %s" % rel)
            for rel in (REGISTRY, MODULES_README, ARIF_MANIFEST, ADAPTERS_README):
                self.assertFalse(os.path.exists(os.path.join(target, rel)),
                                 "an unmodified receipted file must be deleted: %s"
                                 % rel)
            self.assertFalse(os.path.isfile(
                os.path.join(target, pc_support.RECEIPT)),
                "the receipt must be deleted last")
            self.assertFalse(os.path.exists(os.path.join(target, "arif", "adapters")),
                             "an emptied created directory must be removed")
            self.assertTrue(os.path.isdir(
                os.path.join(target, "eldunarya", "eldunari", "demo")),
                "a directory holding a surviving file must be kept")

    def test_remove_never_removes_a_directory_that_holds_user_files(self):
        with tempfile.TemporaryDirectory(prefix="removal-dir-") as work:
            target = initialize(work)
            modules = os.path.join(target, os.path.dirname(MODULES_CANARY))
            write(os.path.join(target, MODULES_CANARY), "keep me\n")

            result = pc_support.run_cli("remove", "--target", target)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(target, MODULES_CANARY)))
            self.assertTrue(os.path.isdir(modules),
                            "modules/ still holds a user file, so it must stay")
            self.assertFalse(os.path.isfile(
                os.path.join(target, MODULES_README)),
                "the scaffold's own stub must still be deleted")
            self.assertTrue(os.path.isdir(
                os.path.join(target, "eldunarya", "eldunari", "demo")))
            self.assertFalse(os.path.exists(os.path.join(target, "arif")),
                             "arif/ holds only created files and empty dirs, so it "
                             "must be gone")

    def test_remove_leaves_an_untouched_target_empty(self):
        with tempfile.TemporaryDirectory(prefix="removal-clean-") as work:
            target = initialize(work)
            result = pc_support.run_cli("remove", "--target", target)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([], os.listdir(target),
                             "a target with no user files must end up empty")
            self.assertIn("result: ok", result.stdout)

    def test_remove_dry_run_reports_the_plan_and_deletes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="removal-dry-") as work:
            target = initialize(work)
            before_files = pc_support.file_map(target)
            before_mtimes = pc_support.mtimes(target)

            result = pc_support.run_cli("remove", "--target", target, "--dry-run")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before_files, pc_support.file_map(target),
                             "--dry-run must delete nothing")
            self.assertEqual(before_mtimes, pc_support.mtimes(target),
                             "--dry-run must not touch any file")
            self.assertIn("would delete: %s" % REGISTRY, result.stdout)
            self.assertIn("result: dry-run, no files deleted", result.stdout)
            self.assertNotIn("deleted:", result.stdout)

    def test_remove_without_a_receipt_exits_2_and_deletes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="removal-noreceipt-") as work:
            target = os.path.join(work, "created")
            os.makedirs(target)
            write(os.path.join(target, ROOT_CANARY), "keep me\n")

            result = pc_support.run_cli("remove", "--target", target)
            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertIn("receipt", result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(target, ROOT_CANARY)))

    def test_a_second_remove_finds_no_receipt_and_exits_2(self):
        with tempfile.TemporaryDirectory(prefix="removal-twice-") as work:
            target = initialize(work)
            self.assertEqual(0, pc_support.run_cli(
                "remove", "--target", target).returncode)
            second = pc_support.run_cli("remove", "--target", target)
            self.assertEqual(2, second.returncode,
                             "remove is scoped to the receipt, and the receipt "
                             "is gone")


if __name__ == "__main__":
    unittest.main()
