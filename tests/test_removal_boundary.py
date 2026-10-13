"""Synthetic receipts must never authorize deletion outside their target."""

import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pc_support


class TestRemovalBoundary(unittest.TestCase):
    def prepare(self, work):
        target = os.path.join(work, "target")
        os.makedirs(os.path.join(target, "nested"))
        inside = os.path.join(target, "nested", "owned.txt")
        outside = os.path.join(work, "outside.txt")
        for path in (inside, outside):
            with open(path, "wb") as handle:
                handle.write(b"synthetic canary\n")
        digest = hashlib.sha256(b"synthetic canary\n").hexdigest()
        document = {"schema": "protean-context-receipt-v1", "schemaVersion": 1,
                    "created": [{"path": "nested/owned.txt", "sha256": digest}],
                    "directories": ["nested"], "migrations": []}
        return target, inside, outside, document, digest

    def assert_refused(self, target, inside, outside, document):
        receipt = os.path.join(target, pc_support.RECEIPT)
        with open(receipt, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        before = pc_support.file_map(os.path.dirname(target))
        for flags in ((), ("--dry-run",)):
            result = pc_support.run_cli("remove", "--target", target, *flags)
            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertIn("invalid receipt", result.stderr)
            self.assertEqual(before, pc_support.file_map(os.path.dirname(target)))
            self.assertTrue(os.path.isfile(inside))
            self.assertTrue(os.path.isfile(outside))
            self.assertTrue(os.path.isfile(receipt))

    def test_invalid_created_paths_preflight_before_any_delete(self):
        for bad in ("../outside.txt", "", ".", "nested/../owned.txt", "nested/./owned.txt", None, 7):
            with self.subTest(path=bad), tempfile.TemporaryDirectory() as work:
                target, inside, outside, doc, digest = self.prepare(work)
                doc["created"].append({"path": bad, "sha256": digest})
                self.assert_refused(target, inside, outside, doc)
        with tempfile.TemporaryDirectory() as work:
            target, inside, outside, doc, digest = self.prepare(work)
            doc["created"].append({"path": outside, "sha256": digest})
            self.assert_refused(target, inside, outside, doc)

    def test_invalid_directory_paths_preflight_before_any_delete(self):
        for bad in ("../empty", "", ".", "nested/../empty", None, 7):
            with self.subTest(path=bad), tempfile.TemporaryDirectory() as work:
                target, inside, outside, doc, _ = self.prepare(work)
                os.mkdir(os.path.join(work, "empty"))
                doc["directories"].append(bad)
                self.assert_refused(target, inside, outside, doc)
                self.assertTrue(os.path.isdir(os.path.join(work, "empty")))
        with tempfile.TemporaryDirectory() as work:
            target, inside, outside, doc, _ = self.prepare(work)
            empty = os.path.join(work, "empty")
            os.mkdir(empty)
            doc["directories"].append(empty)
            self.assert_refused(target, inside, outside, doc)
            self.assertTrue(os.path.isdir(empty))

    def test_escaping_symlink_parents_refused_for_files_and_directories(self):
        for kind in ("created", "directories"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as work:
                target, inside, outside, doc, digest = self.prepare(work)
                os.mkdir(os.path.join(work, "empty"))
                os.symlink(work, os.path.join(target, "link"))
                if kind == "created":
                    doc[kind].append({"path": "link/outside.txt", "sha256": digest})
                else:
                    doc[kind].append("link/empty")
                self.assert_refused(target, inside, outside, doc)
                self.assertTrue(os.path.isdir(os.path.join(work, "empty")))

    def test_invalid_receipt_entry_types_refused(self):
        for field, bad in (("created", "nested/owned.txt"), ("created", [None]),
                           ("created", [{"path": "nested/owned.txt", "sha256": 7}]),
                           ("directories", "nested"), ("directories", None)):
            with self.subTest(field=field, value=bad), tempfile.TemporaryDirectory() as work:
                target, inside, outside, doc, _ = self.prepare(work)
                doc[field] = bad
                self.assert_refused(target, inside, outside, doc)

    def test_escaping_receipt_link_is_refused_without_removing_it(self):
        with tempfile.TemporaryDirectory() as work:
            target, inside, outside, doc, _ = self.prepare(work)
            stored = os.path.join(work, "receipt.json")
            with open(stored, "w", encoding="utf-8") as handle:
                json.dump(doc, handle)
            receipt = os.path.join(target, pc_support.RECEIPT)
            os.symlink(stored, receipt)
            before = pc_support.file_map(work)
            result = pc_support.run_cli("remove", "--target", target)
            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertEqual(before, pc_support.file_map(work))
            self.assertTrue(os.path.islink(receipt))

    def test_intentional_target_root_link_allows_nested_removal(self):
        with tempfile.TemporaryDirectory() as work:
            target, inside, outside, doc, _ = self.prepare(work)
            with open(os.path.join(target, pc_support.RECEIPT), "w", encoding="utf-8") as handle:
                json.dump(doc, handle)
            alias = os.path.join(work, "root-link")
            os.symlink(target, alias)
            result = pc_support.run_cli("remove", "--target", alias)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual([], os.listdir(target))
            self.assertTrue(os.path.isfile(outside))


if __name__ == "__main__":
    unittest.main()
