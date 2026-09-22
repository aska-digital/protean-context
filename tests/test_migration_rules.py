#!/usr/bin/env python3
"""Step 13: upgrade rules are forward-only, additive, backed up, and refuse a downgrade.

Locked rules (decision D4.6), proven against the synthetic v1/v2 fixture pair:

  1. `schemaVersion` is a positive integer; a bad one is exit 2;
  2. migrations are forward-only pairs (n -> n+1) and additive: nothing that
     existed may be removed or changed, and the version must be bumped;
  3. a migration that needs to edit user content fails closed (exit 4) and
     reports the manual step instead of continuing;
  4. a target newer than the template is refused, exit 2, and never downgraded;
  5. a scaffold-owned file is backed up under
     `{TARGET}/.protean-backup/<from>-to-<to>/` before it is replaced.

v1.0.0 ships an EMPTY migration registry, so the mechanism is exercised here
directly through `pc_migrate` (the seam the module documents for exactly this),
plus one end-to-end CLI case for the refused downgrade.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pc_support

sys.path.insert(0, pc_support.SCRIPTS)

import pc_common
import pc_migrate

SCHEMA = "eldunarya-v1"
REGISTRY_REL = "eldunarya/eldunarya.json"
V1_FIXTURE = os.path.join(pc_support.MIGRATION_FIXTURES, "v1", "eldunarya.json")
V2_FIXTURE = os.path.join(pc_support.MIGRATION_FIXTURES, "v2", "eldunarya.json")


def additive_rule(document):
    """The v1 -> v2 rule: add the new field and bump the version."""
    document["registryId"] = "demo-registry"
    document["schemaVersion"] = 2
    return document


def registry_with(rule):
    return {(SCHEMA, 1): rule}


class TestMigrationRules(unittest.TestCase):
    def test_forward_rule_turns_v1_into_the_v2_fixture(self):
        v1 = pc_support.fixture_document(V1_FIXTURE)
        v2 = pc_support.fixture_document(V2_FIXTURE)
        before = pc_support.fixture_document(V1_FIXTURE)

        migrated, applied = pc_migrate.apply_chain(
            v1, SCHEMA, 1, 2, registry=registry_with(additive_rule),
            path=REGISTRY_REL)

        self.assertEqual(v2, migrated,
                         "the registered rule must reproduce the v2 fixture")
        self.assertEqual([{"path": REGISTRY_REL, "from": 1, "to": 2}], applied,
                         "an applied migration must be recorded for the receipt")
        self.assertEqual(before, v1,
                         "the input document must not be mutated in place")

    def test_downgrade_is_refused_with_exit_2(self):
        v2 = pc_support.fixture_document(V2_FIXTURE)
        with self.assertRaises(pc_common.BootstrapError) as caught:
            pc_migrate.apply_chain(v2, SCHEMA, 2, 1, registry={},
                                   path=REGISTRY_REL)
        self.assertEqual(pc_common.EXIT_SCHEMA, caught.exception.code)
        self.assertIn("downgrade refused", caught.exception.message)

    def test_an_unregistered_step_fails_closed_with_exit_4(self):
        v1 = pc_support.fixture_document(V1_FIXTURE)
        with self.assertRaises(pc_common.BootstrapError) as caught:
            pc_migrate.apply_chain(v1, SCHEMA, 1, 2, registry={},
                                   path=REGISTRY_REL)
        self.assertEqual(pc_common.EXIT_INTEGRITY, caught.exception.code)
        self.assertIn("no registered migration", caught.exception.message)
        self.assertIn("nothing was written", caught.exception.message)

    def test_a_rule_that_removes_or_changes_a_field_fails_closed(self):
        v1 = pc_support.fixture_document(V1_FIXTURE)

        def removing(document):
            del document["eldunari"]
            document["schemaVersion"] = 2
            return document

        def changing(document):
            document["eldunari"] = []
            document["schemaVersion"] = 2
            return document

        for rule in (removing, changing):
            with self.subTest(rule=rule.__name__):
                with self.assertRaises(pc_common.BootstrapError) as caught:
                    pc_migrate.apply_chain(v1, SCHEMA, 1, 2,
                                           registry=registry_with(rule))
                self.assertEqual(pc_common.EXIT_INTEGRITY, caught.exception.code)
                self.assertIn("would edit user content", caught.exception.message)

    def test_a_rule_that_does_not_bump_the_version_fails_closed(self):
        v1 = pc_support.fixture_document(V1_FIXTURE)

        def forgetful(document):
            document["registryId"] = "demo-registry"
            return document

        with self.assertRaises(pc_common.BootstrapError) as caught:
            pc_migrate.apply_chain(v1, SCHEMA, 1, 2,
                                   registry=registry_with(forgetful))
        self.assertEqual(pc_common.EXIT_INTEGRITY, caught.exception.code)
        self.assertIn("did not set schemaVersion to 2", caught.exception.message)

    def test_a_broken_rule_never_half_applies(self):
        v1 = pc_support.fixture_document(V1_FIXTURE)

        def broken(document):
            raise RuntimeError("synthetic rule failure")

        with self.assertRaises(pc_common.BootstrapError) as caught:
            pc_migrate.apply_chain(v1, SCHEMA, 1, 2, registry=registry_with(broken))
        self.assertEqual(pc_common.EXIT_INTEGRITY, caught.exception.code)
        self.assertIn("failed", caught.exception.message)

    def test_schema_version_must_be_a_positive_integer(self):
        self.assertEqual(1, pc_migrate.document_version({"schemaVersion": 1}, "x"))
        for bad in (0, -3, "1", None, True, 1.5):
            with self.subTest(value=bad):
                with self.assertRaises(pc_common.BootstrapError) as caught:
                    pc_migrate.document_version({"schemaVersion": bad}, "x")
                self.assertEqual(pc_common.EXIT_SCHEMA, caught.exception.code)

    def test_backup_is_written_under_the_from_to_directory(self):
        with tempfile.TemporaryDirectory(prefix="migration-backup-") as work:
            source = os.path.join(work, REGISTRY_REL)
            os.makedirs(os.path.dirname(source))
            original = '{"schema": "eldunarya-v1", "schemaVersion": 1}\n'
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(original)

            relative = pc_migrate.backup_file(work, REGISTRY_REL, 1, 2)
            self.assertEqual(".protean-backup/v1-to-v2/%s" % REGISTRY_REL, relative)
            backup = os.path.join(work, relative)
            self.assertTrue(os.path.isfile(backup), "the backup must exist")
            self.assertEqual(original, pc_support.read_text(backup),
                             "the backup must be byte-identical to the original")
            self.assertEqual(original, pc_support.read_text(source),
                             "backing up must not modify the original")
            self.assertIsNone(pc_migrate.backup_file(work, "eldunarya/absent.json",
                                                     1, 2),
                              "a missing source has nothing to back up")

    def test_cli_init_refuses_a_downgrade_and_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="migration-cli-") as work:
            target = os.path.join(work, "created")
            self.assertEqual(0, pc_support.run_cli(
                "init", "--target", target, "--name", "demo").returncode)

            registry_path = os.path.join(target, REGISTRY_REL)
            document = pc_support.load_json(registry_path)
            document["schemaVersion"] = 2
            with open(registry_path, "w", encoding="utf-8") as handle:
                handle.write(pc_support.dumps_json(document))

            before_files = pc_support.file_map(target)
            before_mtimes = pc_support.mtimes(target)
            result = pc_support.run_cli("init", "--target", target, "--name", "demo")
            self.assertEqual(pc_common.EXIT_SCHEMA, result.returncode,
                             result.stdout + result.stderr)
            self.assertIn("downgrade refused", result.stderr)
            self.assertEqual(before_files, pc_support.file_map(target),
                             "a refused run must write nothing")
            self.assertEqual(before_mtimes, pc_support.mtimes(target),
                             "a refused run must not touch a file")


if __name__ == "__main__":
    unittest.main()
