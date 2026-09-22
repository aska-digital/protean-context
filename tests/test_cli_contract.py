#!/usr/bin/env python3
"""CLI contract suite: help, the exit-code table, the name rule, and --dry-run.

Covers the parts of the locked CLI contract (decision D5) and its acceptance
evidence (E5.1, E5.3, E3.2) that the behavioral suites do not:

  * `--help` exits 0 and prints usage for the entrypoint and every subcommand;
  * the D5.5 exit-code table is asserted one test per non-zero code, so each
    meaning has a command that produces it: 1 usage or bad or reserved name,
    2 invalid schema or manifest, 3 a missing adapter or prerequisite, 4 a
    conflict on a scaffold file, 5 a write failure, 6 a failing verify check;
  * the naming rule (D3.4, E3.2) accepts and rejects the documented shapes,
    including the three reserved names;
  * `--dry-run` writes nothing, on every command that has a write path.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pc_support

COMMANDS = ("plan", "init", "verify", "ingest", "remove")
REGISTRY = "eldunarya/eldunarya.json"
ADAPTERS_README = "arif/adapters/README.md"

INVALID_ADAPTER = '''\
"""Synthetic adapter that yields one invalid record (test input only)."""

ADAPTER_NAME = "synthetic-invalid-adapter"
ADAPTER_VERSION = "0.0.1"


def collect(source):
    yield {
        "schema": "arif-record-v1",
        "schemaVersion": 1,
        "id": "demo-record-1",
        "source": {"title": "SYNTHETIC TEST DATA", "locator": "sample.txt",
                   "kind": "document", "retrieved": None},
        "content": {"ref": "content/" + "0" * 64, "mediaType": "text/plain",
                    "checksum": "0" * 64, "bytes": 0},
        "metadata": {"topics": [], "tags": [], "language": None, "license": None},
        "provenance": {"adapter": "synthetic-invalid-adapter", "ingestedAt": None,
                       "method": "collect"},
        "embedding": [0.0],
    }
'''

VALID_NAMES = ("a", "ab", "demo", "a1", "a-b", "a" + "b" * 46 + "c")
INVALID_NAMES = ("Bad Name", "Bad", "bad name", "-bad", "bad-", "ba.d", "bad/name",
                 "", "1bad", "a" * 49)


def initialize(target, name="demo"):
    result = pc_support.run_cli("init", "--target", target, "--name", name)
    if result.returncode != 0:
        raise AssertionError("init failed (%d): %s" % (result.returncode,
                                                       result.stderr))
    return target


class TestCliContract(unittest.TestCase):
    def assert_exit(self, expected, result, label):
        self.assertEqual(expected, result.returncode,
                         "%s: expected exit %d, got %d\nstdout:\n%s\nstderr:\n%s"
                         % (label, expected, result.returncode, result.stdout,
                            result.stderr))

    def test_help_exits_zero_and_prints_usage_for_every_command(self):
        top = pc_support.run_cli("--help")
        self.assert_exit(0, top, "bootstrap.py --help")
        self.assertIn("usage", top.stdout.lower())
        for command in COMMANDS:
            with self.subTest(command=command):
                result = pc_support.run_cli(command, "--help")
                self.assert_exit(0, result, "%s --help" % command)
                self.assertIn("usage", result.stdout.lower())
                self.assertIn("--target", result.stdout)

    def test_no_command_is_a_usage_error_with_exit_1(self):
        result = pc_support.run_cli()
        self.assert_exit(1, result, "no command")
        self.assertIn("usage", result.stdout.lower())

    def test_exit_1_usage_bad_name_and_reserved_name(self):
        with tempfile.TemporaryDirectory(prefix="cli-exit1-") as work:
            target = os.path.join(work, "created")
            self.assert_exit(1, pc_support.run_cli(
                "init", "--target", target, "--name", "Bad Name"), "bad name")
            for reserved in ("eldunari", "eldunarya", "arif"):
                with self.subTest(name=reserved):
                    result = pc_support.run_cli("init", "--target", target,
                                                "--name", reserved)
                    self.assert_exit(1, result, "reserved %s" % reserved)
                    self.assertIn("reserved", result.stderr)
            self.assert_exit(1, pc_support.run_cli("init", "--target", target),
                             "init without --name")
            self.assertFalse(os.path.exists(target),
                             "a rejected command must not create the target")

    def test_exit_2_invalid_registry_and_invalid_ingest_are_write_free(self):
        with tempfile.TemporaryDirectory(prefix="cli-exit2-") as work:
            target = initialize(os.path.join(work, "created"))
            registry = os.path.join(target, REGISTRY)
            with open(registry, "w", encoding="utf-8") as handle:
                handle.write("{not json\n")
            before = pc_support.file_map(target)
            result = pc_support.run_cli("init", "--target", target, "--name",
                                        "demo")
            self.assert_exit(2, result, "invalid registry")
            self.assertEqual(before, pc_support.file_map(target),
                             "a schema failure must write nothing")
            self.assert_exit(2, pc_support.run_cli("verify", "--target", target),
                             "verify on an invalid registry")

            adapter = os.path.join(work, "adapter_invalid.py")
            with open(adapter, "w", encoding="utf-8") as handle:
                handle.write(INVALID_ADAPTER)
            fresh = initialize(os.path.join(work, "second"))
            records_dir = os.path.join(fresh, "arif", "records")
            invalid = pc_support.run_cli("ingest", "--target", fresh, "--adapter",
                                         adapter, "--source",
                                         pc_support.SOURCE)
            self.assert_exit(2, invalid, "ingest of an invalid record")
            self.assertEqual([], os.listdir(records_dir),
                             "ingest is all-or-nothing: a rejected run writes no "
                             "record")

    def test_exit_3_missing_adapter_and_missing_prerequisite(self):
        with tempfile.TemporaryDirectory(prefix="cli-exit3-") as work:
            target = initialize(os.path.join(work, "created"))
            missing_adapter = os.path.join(work, "no-such-adapter.py")
            result = pc_support.run_cli("ingest", "--target", target, "--adapter",
                                        missing_adapter, "--source",
                                        pc_support.SOURCE)
            self.assert_exit(3, result, "missing adapter")
            self.assertIn("adapter missing", result.stderr)

            result = pc_support.run_cli("ingest", "--target", target, "--adapter",
                                        pc_support.ADAPTER, "--source",
                                        os.path.join(work, "no-such-source"))
            self.assert_exit(3, result, "missing source")

            uninitialized = os.path.join(work, "plain")
            os.makedirs(uninitialized)
            result = pc_support.run_cli("ingest", "--target", uninitialized,
                                        "--adapter", pc_support.ADAPTER,
                                        "--source", pc_support.SOURCE)
            self.assert_exit(3, result, "ingest without a receipt")

    def test_exit_4_conflict_on_a_scaffold_file_keeps_the_user_file(self):
        with tempfile.TemporaryDirectory(prefix="cli-exit4-") as work:
            target = initialize(os.path.join(work, "created"))
            path = os.path.join(target, ADAPTERS_README)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("user edit\n")
            result = pc_support.run_cli("init", "--target", target, "--name",
                                        "demo")
            self.assert_exit(4, result, "conflict on a scaffold file")
            self.assertIn("conflict: %s" % ADAPTERS_README, result.stdout)
            self.assertIn("user edit", pc_support.read_text(path),
                          "a conflicting file must be left exactly as the user "
                          "wrote it")

    def test_exit_5_write_failure(self):
        with tempfile.TemporaryDirectory(prefix="cli-exit5-") as work:
            blocker = os.path.join(work, "blocker")
            with open(blocker, "w", encoding="utf-8") as handle:
                handle.write("not a directory\n")
            target = os.path.join(blocker, "nested")
            result = pc_support.run_cli("init", "--target", target, "--name",
                                        "demo")
            self.assert_exit(5, result, "unwritable target")
            self.assertIn("error:", result.stderr)
            self.assertIn(target, result.stderr)
            self.assertFalse(os.path.exists(target))

    def test_exit_6_verify_failure(self):
        with tempfile.TemporaryDirectory(prefix="cli-exit6-") as work:
            target = initialize(os.path.join(work, "created"))
            self.assert_exit(0, pc_support.run_cli("verify", "--target", target),
                             "verify on a healthy target")
            os.remove(os.path.join(target, REGISTRY))
            result = pc_support.run_cli("verify", "--target", target)
            self.assert_exit(6, result, "verify after tampering")
            self.assertIn("FAILED", result.stdout)

    def test_name_rule_accepts_the_documented_shapes(self):
        for name in VALID_NAMES:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(prefix="cli-name-") as work:
                    target = os.path.join(work, "created")
                    result = pc_support.run_cli("init", "--target", target,
                                                "--name", name)
                    self.assert_exit(0, result, "name %r" % name)
                    self.assertTrue(os.path.isfile(os.path.join(
                        target, "eldunarya", "eldunari", name, "ROUTER.md")),
                        "the named Eldunari tree must exist for %r" % name)

    def test_name_rule_rejects_every_documented_violation(self):
        for name in INVALID_NAMES:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(prefix="cli-name-bad-") as work:
                    target = os.path.join(work, "created")
                    # The --name=<value> form keeps argparse from reading a
                    # leading-hyphen value as an option, so the naming rule
                    # itself is what rejects it (exit 1, not a usage error).
                    result = pc_support.run_cli("init", "--target", target,
                                                "--name=%s" % name)
                    self.assert_exit(1, result, "name %r" % name)
                    self.assertFalse(os.path.exists(target))

    def test_dry_run_writes_nothing_on_every_write_path(self):
        with tempfile.TemporaryDirectory(prefix="cli-dry-") as work:
            target = os.path.join(work, "created")
            planned = pc_support.run_cli("init", "--target", target, "--name",
                                         "demo", "--dry-run")
            self.assert_exit(0, planned, "init --dry-run")
            self.assertFalse(os.path.exists(target),
                             "init --dry-run must not create the target")
            self.assertIn("result: dry-run, no files written", planned.stdout)

            initialize(target)
            before = pc_support.file_map(target)
            before_mtimes = pc_support.mtimes(target)
            ingest = pc_support.run_cli("ingest", "--target", target, "--adapter",
                                        pc_support.ADAPTER, "--source",
                                        pc_support.SOURCE, "--dry-run")
            self.assert_exit(0, ingest, "ingest --dry-run")
            self.assertIn("no files written", ingest.stdout)
            remove = pc_support.run_cli("remove", "--target", target, "--dry-run")
            self.assert_exit(0, remove, "remove --dry-run")
            self.assertIn("no files deleted", remove.stdout)
            self.assertEqual(before, pc_support.file_map(target),
                             "--dry-run must write nothing and delete nothing")
            self.assertEqual(before_mtimes, pc_support.mtimes(target))

    def test_offline_is_accepted_and_reported_on_every_command(self):
        with tempfile.TemporaryDirectory(prefix="cli-offline-") as work:
            target = os.path.join(work, "created")
            for command, extra in (("plan", ["--name", "demo"]),
                                   ("init", ["--name", "demo"]),
                                   ("verify", []),
                                   ("remove", ["--dry-run"])):
                with self.subTest(command=command):
                    result = pc_support.run_cli(command, "--target", target,
                                                "--offline", *extra)
                    self.assert_exit(0, result, "%s --offline" % command)
                    self.assertIn("offline", result.stdout)


if __name__ == "__main__":
    unittest.main()
