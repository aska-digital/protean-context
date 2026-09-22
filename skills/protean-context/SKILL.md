---
name: protean-context
description: Versioned empty scaffolds and a stdlib-only bootstrap CLI that initialize a user-owned Eldunarya knowledge tree and Arif knowledge base with no bundled data.
version: 1.0.0
license: MIT
---

# protean-context

Discoverability and operator instructions only. This skill ships no runtime code:
the runnable part of the ingredient is `scripts/protean-context/bootstrap.py`, and
this file tells you when to use it and how to read its results.

## What this is

Versioned empty scaffolds and a stdlib-only bootstrap CLI that initialize a
user-owned Eldunarya knowledge tree and Arif knowledge base with no bundled data.
The full description, the directory map, and the release notes live in
`README.md` at the root of this ingredient (one fact, one home: this file points
there instead of repeating it).

## Use when

- You need an empty Eldunarya tree (a registry plus one directory per named
  Eldunari) or an empty Arif store (records, content, index, adapters) that
  ships with no bundled content.
- You want deterministic, offline verification of that structure.
- You are installing this ingredient either standalone with `install.sh` or
  through the pinned composer.

## Skip when

- You want a bundled database, index, corpus, or precomputed embeddings. None
  ship, by contract.
- You want a plugin or MCP runtime surface. This ingredient is files plus a
  stdlib CLI.
- You want the scaffold to read anything by default. It reads only the explicit
  `--source` you pass to `ingest`, and it writes only under `--target`.

## Commands

Every command takes an explicit `--target`; there is no hidden default. Run the
CLI from the directory where this ingredient is installed:

```
python3 scripts/protean-context/bootstrap.py plan   --target {TARGET} --name demo
python3 scripts/protean-context/bootstrap.py init   --target {TARGET} --name demo
python3 scripts/protean-context/bootstrap.py verify --target {TARGET}
python3 scripts/protean-context/bootstrap.py ingest --target {TARGET} --adapter <file> --source <path>
python3 scripts/protean-context/bootstrap.py remove --target {TARGET} --dry-run
```

- `plan` is `init --dry-run` as a named command. `--dry-run` exists on every
  command, and `--offline` is accepted everywhere.
- `init` requires at least one `--name` and is ensure-exist per file: absent
  files are created, byte-identical files are reported unchanged, and a
  different file is never overwritten.
- Read the exit code, not just the text: 0 ok, 1 usage or bad or reserved
  `--name`, 2 invalid schema, manifest, or registry, or a refused downgrade,
  3 adapter missing or unimportable or a missing prerequisite, 4 a conflict, a
  hash mismatch, or a migration that would edit your content, 5 a write failure,
  6 a failing or skipping `verify` check. Errors go to stderr, the summary to
  stdout, and no partial success exits 0.

## Operator notes

- A run that reports `conflict: <path>` exits 4 and leaves that file exactly as
  you wrote it. The registry is the one document `init` merges rather than
  skips, because appending an entry for a requested name is the documented
  ensure-exist behavior.
- `remove` is scoped to the init receipt: it deletes exactly the paths that
  `init` created, and only while their hash still matches. Somebody else's file
  is never touched, and directories are removed only when empty.
- `verify` answers the health question; a check it cannot evaluate is a failure,
  never a pass.
- If a scaffold-owned file's version is newer than the installed scaffold,
  `init` refuses with exit 2 and never downgrades. Upgrades are forward-only,
  additive, and backed up first under `{TARGET}/.protean-backup/`.

## Pointers

- `README.md` (ingredient root): contract line, directory map, gate list, limits.
- `templates/protean-context/docs/rehoming.md`: tokens, the one environment
  override, linking an Eldunari to a profile by pointer, Arif store and index
  configuration, backup, upgrade, and removal.
- `templates/protean-context/arif/adapters/README.md`: the adapter contract and
  the locked negative contract, stated once.
- `build/verify-all.py`: the ordered gate runner; its docstring is authoritative.
