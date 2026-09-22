#!/usr/bin/env python3
"""Step 11: two independent inits into different directories are identical.

Global invariant G-I6: `init` writes no timestamp, no machine value, and no
absolute path into anything it creates, so the same arguments always produce the
same bytes. The test proves it twice over:

  * byte level: the per-file sha256 map and the one tree digest of two
    independently created targets are equal, and equal again for a third
    target created later, in a different parent directory;
  * negative level: no created file carries the target's own path, and no
    machine-generated document carries an ISO-8601 timestamp.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pc_support

REGISTRY = "eldunarya/eldunarya.json"
ARIF_MANIFEST = "arif/arif.json"
ISO_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
GENERATED_DOCUMENTS = (REGISTRY, ARIF_MANIFEST, pc_support.RECEIPT)


def init_into(parent, leaf):
    target = os.path.join(parent, leaf)
    result = pc_support.run_cli("init", "--target", target, "--name", "demo")
    if result.returncode != 0:
        raise AssertionError("init failed (%d): %s"
                             % (result.returncode, result.stderr))
    return target


class TestDeterministicInit(unittest.TestCase):
    def test_two_independent_targets_are_byte_identical(self):
        with tempfile.TemporaryDirectory(prefix="deterministic-a-") as first_work:
            with tempfile.TemporaryDirectory(prefix="deterministic-b-") as second_work:
                first = init_into(first_work, "created")
                second = init_into(second_work, "created")

                first_files = pc_support.file_map(first)
                second_files = pc_support.file_map(second)
                self.assertTrue(first_files, "init must create files")
                self.assertEqual(first_files, second_files,
                                 "two independent inits must be byte-identical")
                self.assertEqual(pc_support.tree_digest(first),
                                 pc_support.tree_digest(second),
                                 "two independent inits must have one tree hash")

    def test_tree_digest_is_stable_for_a_later_target(self):
        with tempfile.TemporaryDirectory(prefix="deterministic-a-") as first_work:
            first = init_into(first_work, "created")
            digest = pc_support.tree_digest(first)
            with tempfile.TemporaryDirectory(prefix="deterministic-c-") as later_work:
                later = os.path.join(later_work, "nested", "created")
                result = pc_support.run_cli("init", "--target", later,
                                            "--name", "demo")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(digest, pc_support.tree_digest(later),
                                 "a target created later in another directory "
                                 "must hash the same")

    def test_created_files_carry_no_absolute_path(self):
        with tempfile.TemporaryDirectory(prefix="deterministic-path-") as work:
            target = init_into(work, "created")
            for rel in sorted(pc_support.file_map(target)):
                text = pc_support.read_text(os.path.join(target, rel))
                self.assertNotIn(target, text,
                                 "%s carries the target path" % rel)
                self.assertNotIn(work, text,
                                 "%s carries the working directory path" % rel)

    def test_generated_documents_carry_no_timestamp(self):
        with tempfile.TemporaryDirectory(prefix="deterministic-time-") as work:
            target = init_into(work, "created")
            for rel in GENERATED_DOCUMENTS:
                text = pc_support.read_text(os.path.join(target, rel))
                self.assertIsNone(ISO_TIMESTAMP_RE.search(text),
                                  "%s carries an ISO-8601 timestamp, so a rerun "
                                  "could not be byte-identical" % rel)

    def test_receipt_records_only_relative_paths(self):
        with tempfile.TemporaryDirectory(prefix="deterministic-slip-") as work:
            target = init_into(work, "created")
            document = pc_support.load_json(
                os.path.join(target, pc_support.RECEIPT))
            self.assertEqual("protean-context-receipt-v1", document["schema"])
            self.assertEqual(1, document["schemaVersion"])
            paths = [entry["path"] for entry in document["created"]]
            self.assertTrue(paths, "the receipt must list what init created")
            for rel in paths:
                self.assertFalse(os.path.isabs(rel),
                                 "the receipt must carry a relative path: %r" % rel)
                self.assertEqual(os.path.normpath(rel), rel)
                self.assertTrue(os.path.isfile(os.path.join(target, rel)),
                                "every receipted path must exist: %s" % rel)
            for rel in document["directories"]:
                self.assertTrue(os.path.isdir(os.path.join(target, rel)),
                                "every receipted directory must exist: %s" % rel)


if __name__ == "__main__":
    unittest.main()
