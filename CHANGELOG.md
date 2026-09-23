# Changelog

All notable changes to this repository are documented here. The format follows the kit convention: one entry per released version, newest first.

## 1.1.0

This release names and documents the zero-context recovery pattern that the
scaffold already implements, and adds operator guidance for entering agents
and writers.

Added:

- README section naming zero-context recovery, the cold-start contents, and
  the fixed load order of registry, one router, and one module.
- Entering-agent instructions in the ROUTER template: read this file first,
  resolve exactly one pointer per task, never load all modules, and report an
  unresolvable pointer as a defect.
- Population discipline in the modules README template: one fact one home,
  relative pointers never copies, and verify by read-back from disk.
- Operator and agent guide `templates/protean-context/docs/zero-context.md`
  with the cold-start loop, the pointer rules, and a synthetic worked
  example.
- Router-discipline verification over initialized targets: unresolvable
  pointers and homeless pointers fail the check.

## 1.0.0

Stable release. No schema, scaffold, or CLI behavior changes from the 0.1.0 beta; this release promotes the beta to stable.

Changed:

- Version bump 0.1.0 to 1.0.0 across the ingredient descriptor, `install.sh`, the skill frontmatter, README, and code comments.
- Repository metadata completed: full description, topics, wiki disabled to match sibling ingredients.

## 0.1.0

First release, published as a prerelease.

Added:

- Eldunarya empty scaffold template: `eldunarya.json` registry, the per-Eldunari `ROUTER.md` template and `modules/` stub, and schema documents `eldunarya-v1` and `eldunari-v1`.
- Arif empty scaffold template: `arif.json` store manifest (schema `arif-store-v1`), the metadata-first record schema (`arif-record-v1`), the empty `records/`, `content/`, and `index/` layout, and `adapters/README.md`.
- stdlib-only bootstrap CLI (`scripts/protean-context/bootstrap.py`) with `plan`, `init`, `verify`, `ingest`, and `remove`. Every command requires an explicit `--target`. Exit codes follow the kit 0 to 6 convention.
- Deterministic gate runner `build/verify-all.py` with 14 ordered steps that fail closed, plus the composer post-install gate `gates/protean-context/check-post-install.py`.
- Standalone `install.sh` (bash and coreutils, `--target`, `--dry-run`, no network) and the ingredient descriptor `protean-ingredient.json`.
- Re-homing and configuration guide `templates/protean-context/docs/rehoming.md` with one environment override and token-only path placeholders.
- Skill surface `skills/protean-context/SKILL.md` for discoverability and operator instructions only; no plugin and no MCP surface.
- Synthetic fixtures only, each carrying the `SYNTHETIC TEST DATA` header marker.

Notes:

- No migration ships in 0.1.0. The forward-only migration mechanism is specified and proven against a synthetic schema pair.
- Composition into `protean-kit` lands through a separate reviewed lock-entry pull request after this repository's own gates and the compatibility proof pass.
