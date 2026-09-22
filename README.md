Versioned empty scaffolds and a stdlib-only bootstrap CLI that initialize a user-owned Eldunarya knowledge tree and Arif knowledge base with no bundled data.
# protean-context

## Summary

This repository ships versioned empty scaffolds for two user-owned context systems and a stdlib-only bootstrap CLI that initializes them. An Eldunarya is the user-owned collection of one or more named Eldunari. An Eldunari is a plain directory tree of versioned markdown knowledge with a fixed schema and no bundled content. Initialization creates the empty tree in a directory the user selects, and every later write belongs to the user. Arif is the user-owned external knowledge base. The scaffold defines its storage contract, ingestion adapter boundary, metadata-first record fields, embedding configuration slot, and upgrade path, and it bundles no database, no index, and no corpus. Fixtures are synthetic only, and initialization never reads live state.

## Do you need this

ROLE

The context ingredient of protean-kit: empty, versioned scaffold templates for an Eldunarya and an Arif store, a stdlib-only bootstrap CLI that initializes both into a directory you select, and deterministic gates that prove emptiness, privacy, path portability, idempotent reruns, and non-destructive removal.

USE WHEN

- You want to initialize a user-owned Eldunarya knowledge tree and an Arif knowledge base that ship with no bundled content.
- You want offline, deterministic verification of that structure (14 ordered gates, fail closed).
- You install context tooling through the pinned protean-kit composer, or install this ingredient standalone with its own `install.sh`.

SKIP WHEN

- You want a bundled database, index, corpus, or precomputed embeddings. None ship, by contract.
- You want a plugin or MCP runtime surface. This ingredient is files plus a stdlib CLI.
- You want automatic ingestion from your machine. The scaffold reads nothing except the explicit `--source` you pass to `ingest`, and it writes nothing outside `--target`.

## What is inside

```
protean-context/
  README.md                        line 1 is the contract sentence (see License and gate 1)
  LICENSE                          committed LICENSE file is authoritative (MIT)
  CHANGELOG.md                     release-notes source
  protean-ingredient.json          ingredient descriptor: contract line, installTargets, gates
  install.sh                       standalone installer: --target, --dry-run, no network
  skills/
    protean-context/
      SKILL.md                     discoverability and operator instructions only, no runtime
  scripts/
    protean-context/
      bootstrap.py                 stdlib-only CLI: plan, init, verify, ingest, remove
  templates/
    protean-context/
      eldunarya/
        eldunarya.json             registry template (schema eldunarya-v1)
        eldunari/
          ROUTER.template.md       materialized as eldunari/<name>/ROUTER.md by init
          modules/
            README.template.md     materialized as modules/README.md by init
      arif/
        arif.json                  store manifest template (schema arif-store-v1)
        adapters/
          README.md                adapter contract summary
        records/                   empty at ship
        content/                   empty at ship
        index/                     empty at ship
      schema/
        eldunarya.schema.json
        eldunari.schema.json
        arif-store.schema.json
        arif-record.schema.json
      docs/
        rehoming.md                re-homing and configuration guide (section 7)
  gates/
    protean-context/
      check-manifest-parity.py     gate 1
      check-schema.py              gate 2
      check-emptiness.py           gate 3
      check-leak-scan.py           gate 4
      check-path-portability.py    gate 5
      check-identifiers.py         gate 6
      check-stdlib-imports.py      gate 7
      check-synthetic-fixtures.py  gate 8
      fresh-install-test.py        gate 14
      check-post-install.py        composer post-install gate (run by the kit)
  fixtures/                        synthetic test data only
  tests/                           unittest suites (kit tests convention)
  build/
    verify-all.py                  ordered gate runner, docstring is authoritative
```

Source directories map 1:1 onto install targets. The descriptor's four install targets are `skills/protean-context`, `scripts/protean-context`, `templates/protean-context`, and `gates/protean-context`. `install.sh` copies them and reads back hashes; it prints every path it writes. The skill is the smallest discoverability and task-time routing surface and contains no runtime code. There is no plugin file and no MCP configuration anywhere in this repository.

## How you use it

Run the CLI from a checkout of this repository (after `install.sh`, the same entry point sits at `scripts/protean-context/bootstrap.py` under the install location you chose). Every command takes an explicit `--target`; there is no hidden default.

```
python3 scripts/protean-context/bootstrap.py plan   --target {TARGET} --name demo
python3 scripts/protean-context/bootstrap.py init   --target {TARGET} --name demo
python3 scripts/protean-context/bootstrap.py verify --target {TARGET}
```

- `plan` prints the writes `init` would perform and writes nothing. It is `init --dry-run` as a named command. `--dry-run` exists on every command.
- `init` requires at least one `--name` (repeat the flag to ensure several Eldunari). It is ensure-exist per file: absent files are created, byte-identical files are reported unchanged, and different files are never overwritten. A second `init` with the same arguments performs zero writes and exits 0.
- `verify` runs the scaffold checks against `--target` and exits 6 if any check fails or skips.
- `--offline` is accepted everywhere and is truthful by construction: no shipped code imports network modules.

Advanced, always explicit:

```
python3 scripts/protean-context/bootstrap.py ingest --target {TARGET} --adapter <file> --source <path>
python3 scripts/protean-context/bootstrap.py remove --target {TARGET}
```

- `ingest` imports exactly one adapter module you pass by path, validates every record it yields (fail closed, all or nothing), and writes only under `{TARGET}/arif/`. See `templates/protean-context/arif/adapters/README.md`.
- `remove` deletes only the paths listed in the init receipt whose current hash still matches. Both commands accept `--dry-run`.

Exit codes (CLI):

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | usage, bad `--name`, reserved name |
| 2 | schema, manifest, or registry invalid; downgrade refused |
| 3 | adapter missing or unimportable; missing prerequisite |
| 4 | hash mismatch, conflict on a scaffold file, migration would edit user content |
| 5 | write failure (permissions, full disk) |
| 6 | `verify` found a failing or skipping gate |

Errors go to stderr, the summary goes to stdout, and no partial success ever exits 0.

## The Eldunarya empty scaffold

`init` always creates both subsystems. The Eldunarya side of a created target looks like this:

```
{TARGET}/
  .protean-context-receipt.json
  eldunarya/
    eldunarya.json
    eldunari/
      <name>/
        ROUTER.md
        modules/
          README.md
  arif/
```

- One or more named Eldunari: every `init` call requires at least one `--name`. Adding an Eldunari later is `init` again with the additional name; re-running with a name that already exists is a no-op, not an error.
- Naming rule: `^[a-z]([a-z0-9-]{0,46}[a-z0-9])?$` (1 to 48 characters, lowercase, digits, inner hyphens). The names `eldunari`, `eldunarya`, and `arif` are reserved and rejected with exit 1 because they collide with the tree's own directory vocabulary.
- `eldunarya.json` is the registry: schema `eldunarya-v1`, and one entry per name with its relative path and router path. A registry entry whose directory is missing is repaired by re-running `init` with that name.
- `ROUTER.md` is the hot path: identity, hard rules, and pointers only. `modules/` holds the payload. The one-fact-one-home invariant is stated in `modules/README.md`.
- Intentionally absent: no bundled content, no project facts, no procedures, no history, no configuration values. The repository ships no named Eldunari; the template directory holds only the two template files, and every later write belongs to you.

## The Arif empty scaffold

The Arif side of a created target:

```
{TARGET}/
  arif/
    arif.json
    records/          one JSON file per record, metadata first
    content/          content-addressed blobs: content/<sha256>
    index/            derived, rebuildable, empty at init
    adapters/
      README.md
```

- Storage contract: `store.kind` is `file-v1`, stdlib-only, records on disk. No database, no server, no index, and no corpus is bundled or started.
- Metadata-first records (schema `arif-record-v1`): `id`, `source`, `content`, `metadata`, `provenance`, `embedding`. Readers answer source, topic, and provenance questions from metadata without loading content blobs. `content.ref` must resolve inside `content/`; the scaffold never invents timestamps and never rewrites ids.
- Ingestion adapter boundary: you implement one Python module (`ADAPTER_NAME`, `ADAPTER_VERSION`, `collect(source)`) and pass it explicitly with `--adapter <file>`; the CLI validates every yielded record against `arif-record-v1` and writes all records or none. What the scaffold never does is stated verbatim in `templates/protean-context/arif/adapters/README.md`, the single home of that contract.
- Embedding slot: `arif.json` carries an `embedding` object, default `enabled` false with null provider, model, and dimensions. While disabled, no record carries an embedding and `index/` stays empty. Enabling it is your edit plus your adapter work; the scaffold computes nothing and ships no default model.
- Upgrade path: schema versions are compared on rerun; migrations are forward-only, additive, and backed up before replacement; a downgrade is refused with exit 2. Version 1.0.0 ships an empty migration registry, proven against a synthetic fixture pair.

## Re-homing and configuration

Everything this scaffold manages lives under `{TARGET}`, and Hermes configuration lives under `{HERMES_HOME}` (default `{HOME}/.hermes`, overridable once via the `HERMES_HOME` environment variable) with profiles at `{HERMES_HOME}/profiles/{PROFILE_NAME}/`.

The full guide ships with the ingredient: [templates/protean-context/docs/rehoming.md](templates/protean-context/docs/rehoming.md). It covers the token table, the single environment override, linking an Eldunari to a profile by pointer instead of by copy, the `arif.json` store and index walkthrough, changing Hermes settings with `hermes -p {PROFILE_NAME} config set <key> <value>` (never hand-edit `config.yaml`; back it up first because `config set` strips comments), backup by copying `{TARGET}`, and upgrade and removal semantics.

## Verify this release

Run everything from the repository root:

```
python3 build/verify-all.py
```

`verify-all.py` runs the 14 steps below in order with a 300-second timeout per step and exits 0 only when every step exits 0.

Gate exit codes (gate scripts): 0 = pass, 1 = fail, 2 = missing source data. On exit 2 the runner prints `SKIPPED: missing <path>` and counts the step as NOT PASS, so a skip can never produce a green run. The unittest steps exit 0 on pass and non-zero on failure.

Ordered steps, each runnable on its own:

1. Contract line byte parity across README line 1, the descriptor, and the gate list; every named gate exists.

   `python3 gates/protean-context/check-manifest-parity.py`
2. All shipped JSON parses; every schema doc carries `schema` and `schemaVersion`; templates validate; record pointers resolve.

   `python3 gates/protean-context/check-schema.py`
3. No bundled content: shipped and init-created trees contain only allowlisted files; `records/`, `content/`, and `index/` are empty; embedding is disabled.

   `python3 gates/protean-context/check-emptiness.py`
4. Privacy scan: no absolute home paths, no credential value shapes, no owner-content markers in content, filenames, script paths, or config defaults.

   `python3 gates/protean-context/check-leak-scan.py`
5. Path portability: only `{HOME}`, `{TARGET}`, `{HERMES_HOME}`, and `{PROFILE_NAME}` appear as placeholder tokens; no bare `~` default; no absolute paths in defaults.

   `python3 gates/protean-context/check-path-portability.py`
6. Identifiers scan: no internal identity terms outside the documented `public_system_terms` allowlist, each entry citing the decision record.

   `python3 gates/protean-context/check-identifiers.py`
7. Stdlib-only imports proven by AST; network modules hard-forbidden.

   `python3 gates/protean-context/check-stdlib-imports.py`
8. Every fixture carries the `SYNTHETIC TEST DATA` header marker and synthetic entity names only.

   `python3 gates/protean-context/check-synthetic-fixtures.py`
9. No live-state reads and write confinement under an audit-hook sandbox with a canary home tree.

   `python3 -m unittest tests.test_no_live_state`
10. Rerunning `init` changes zero bytes.

    `python3 -m unittest tests.test_idempotent_rerun`
11. Two independent inits produce identical tree hashes.

    `python3 -m unittest tests.test_deterministic_init`
12. `remove` deletes only receipt-listed unmodified paths; canaries and user edits survive.

    `python3 -m unittest tests.test_removal`
13. Upgrade is forward-only, additive, and backed up; downgrade is refused.

    `python3 -m unittest tests.test_migration_rules`
14. Fresh-user proof: worktree copy of HEAD, `install.sh` into a temp target, then `plan`, `init`, and `verify` end to end, offline.

    `python3 gates/protean-context/fresh-install-test.py`

The kit also runs `python3 gates/protean-context/check-post-install.py .` after staging, with the working directory set to the install target; it asserts the four installed targets exist and the installed README line 1 matches the contract.

## Fixtures

Every file under `fixtures/` (and any fixtures under `tests/`) carries a `SYNTHETIC TEST DATA` header marker and uses only synthetic entity names; gate 8 enforces both. Real corpus is forbidden: no fixture contains a real person, place, document, or date. The migration mechanism ships against a synthetic schema pair, not against user data. Fixtures are test inputs only; `init` never reads them.

## Install, upgrade, backup, removal

Install:

```
bash install.sh --target {TARGET} --dry-run
bash install.sh --target {TARGET}
```

`install.sh` takes an explicit `--target` (the directory that receives the ingredient files), prints every path it writes, uses only bash and coreutils, and touches no network. Once this ingredient is pinned in `protean-kit`, the kit's own `install.sh` stages the same four targets and runs the post-install gate.

Upgrade: update your installed copy, then rerun `init` with your names. Scaffold-owned files that still match their init-receipt hash are replaced, and the old copy is kept first under `{TARGET}/.protean-backup/<from>-to-<to>/`. Files you modified are never touched, only reported. A target `schemaVersion` newer than the template is refused with exit 2; downgrade is never attempted.

Backup: the whole `{TARGET}` is the state. Copy the directory. Nothing this scaffold manages is written outside it.

Removal:

```
python3 scripts/protean-context/bootstrap.py remove --target {TARGET} --dry-run
python3 scripts/protean-context/bootstrap.py remove --target {TARGET}
```

`remove` deletes exactly the receipt-listed paths whose current hash still matches. A user-modified path is skipped and reported, an unlisted file is never touched, directories are removed only when empty, and the receipt is deleted last.

## Limits and open items

- No bundled database, index, corpus, or embeddings; no default embedding model.
- No credential values: configuration examples use key names only.
- No live-state ingestion: nothing outside the explicit `--target` and `--source` is read or written (gate 9).
- No plugin runtime and no MCP surface; absence is proven by read-back, not by claim.
- No network access in any shipped code; network modules are hard-forbidden (gate 7).
- Version 1.0.0 ships an empty migration registry; the mechanism is specified and fixture-tested now.
- Composition into `protean-kit` happens only through a lock entry that passes the compatibility proof and the ordered gate sequence; this repository alone does not claim kit membership.

## License

The committed `LICENSE` file in this repository is authoritative. It is the MIT license.

Engine: Hermes by Nous Research, MIT license. This is not a fork; we build on top of it.
