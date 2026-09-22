"""Forward-only, additive, backed-up migration mechanism (decision D4.6).

Rules, all locked:

1. `schemaVersion` is a positive integer; each scaffold release ships exactly
   one version of each schema.
2. Migrations are forward-only, registered as pairs (n -> n+1), and additive:
   new fields get defaults, existing values are preserved. A migration that
   would need to edit user-authored content fails closed (exit 4) and reports
   the manual step instead.
3. A scaffold-owned file that matches its init-receipt hash may be replaced
   during upgrade, after the old copy is kept under
   `{TARGET}/.protean-backup/<from>-to-<to>/`.
4. A target `schemaVersion` newer than the template is refused, exit 2.
   Downgrade is never attempted.
5. The receipt records applied migrations.

v0.1.0 ships an EMPTY registry. The mechanism below is proven against a
synthetic v1-to-v2 fixture pair in tests/test_migration_rules.py; a release
that ships a migration adds one entry to MIGRATIONS and nothing else.
"""

import json
import os

from pc_common import (EXIT_INTEGRITY, EXIT_INSTALL, fail, read_bytes, read_text,
                       sha256_bytes)
from pc_schema import load_json

# Empty in v0.1.0 by design.
MIGRATIONS = {}

BACKUP_DIR = ".protean-backup"


def clone(document):
    """A deep copy of a JSON document.

    Stdlib only: the `copy` module is outside the frozen import allowlist that
    gate 7 enforces, and a JSON round trip is exact for the document shapes this
    mechanism moves (objects, arrays, strings, numbers, booleans, null).
    """
    return json.loads(json.dumps(document))


def registered(schema_name, from_version, registry=None):
    """Return the registered rule for (schema, n -> n+1), or None."""
    table = MIGRATIONS if registry is None else registry
    return table.get((schema_name, from_version))


def check_additive(before, after, schema_name, from_version):
    """Additive-only invariant: nothing that existed may be changed or removed."""
    problems = []
    if not isinstance(after, dict):
        return ["migration for %s v%d returned %s, expected an object"
                % (schema_name, from_version, type(after).__name__)]
    for key in sorted(before):
        if key not in after:
            problems.append("migration for %s v%d removed field %r"
                            % (schema_name, from_version, key))
        elif key == "schemaVersion":
            # The version bump is the migration's purpose; its exact value is
            # checked separately below, so it is not a user-content edit.
            continue
        elif after[key] != before[key]:
            problems.append("migration for %s v%d changed the value of field %r"
                            % (schema_name, from_version, key))
    if after.get("schemaVersion") != from_version + 1:
        problems.append("migration for %s v%d did not set schemaVersion to %d"
                        % (schema_name, from_version, from_version + 1))
    return problems


def apply_chain(document, schema_name, from_version, to_version, registry=None,
                path=""):
    """Apply the registered chain n -> n+1; return (document, applied steps)."""
    label = path or schema_name
    if to_version <= from_version:
        fail(2, "downgrade refused: %s is at schemaVersion %d, the template is at %d"
             % (label, from_version, to_version))
    current = clone(document)
    applied = []
    version = from_version
    while version < to_version:
        rule = registered(schema_name, version, registry)
        if rule is None:
            fail(EXIT_INTEGRITY,
                 "no registered migration for %s v%d -> v%d: this upgrade needs a "
                 "manual step, nothing was written" % (label, version, version + 1))
        try:
            updated = rule(clone(current))
        except Exception as exc:  # a broken rule must never half-apply
            fail(EXIT_INTEGRITY, "migration for %s v%d -> v%d failed: %s"
                 % (label, version, version + 1, exc))
        problems = check_additive(current, updated, schema_name, version)
        if problems:
            fail(EXIT_INTEGRITY,
                 "migration would edit user content, refusing to continue: %s"
                 % "; ".join(problems))
        current = updated
        applied.append({"path": path or schema_name,
                        "from": version, "to": version + 1})
        version += 1
    return current, applied


def backup_rel(from_version, to_version):
    return "%s/v%d-to-v%d" % (BACKUP_DIR, from_version, to_version)


def backup_file(target, rel, from_version, to_version):
    """Copy the current file into the backup directory; return the backup path."""
    source = os.path.join(target, rel)
    if not os.path.isfile(source):
        return None
    rel_backup = "%s/%s" % (backup_rel(from_version, to_version), rel)
    destination = os.path.join(target, rel_backup)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    try:
        data = read_text(source).encode("utf-8")
        with open(destination, "wb") as handle:
            handle.write(data)
    except OSError as exc:
        fail(EXIT_INSTALL, "backup failed for %s (%s)" % (rel, exc))
    if sha256_bytes(data) != sha256_bytes(read_bytes(destination)):
        fail(EXIT_INSTALL, "read-back mismatch after backing up %s" % rel)
    return rel_backup


def document_version(document, label):
    """Read schemaVersion from a parsed document; a bad value is exit 2."""
    if not isinstance(document, dict):
        fail(2, "invalid input: %s is not a JSON object" % label)
    version = document.get("schemaVersion")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        fail(2, "invalid input: %s has no positive integer schemaVersion" % label)
    return version


def load_document(path, label):
    return load_json(path, label)
