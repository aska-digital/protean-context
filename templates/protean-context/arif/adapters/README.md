# Arif ingestion adapters

This directory documents the adapter contract. The scaffold ships no adapters and no sources; you implement an adapter and pass it explicitly.

## What you implement

One Python module, passed to the CLI explicitly by path (`--adapter <file>`), exposing exactly:

```
ADAPTER_NAME: str          # stable identifier recorded in provenance.adapter
ADAPTER_VERSION: str
def collect(source: str) -> Iterable[dict]   # yields arif-record-v1-shaped dicts, embedding always null
```

`collect` yields records shaped like `arif-record-v1` (schema `arif-record-v1`, `schemaVersion` 1): `id`, `source`, `content`, `metadata`, `provenance`, `embedding`. Every yielded record carries `"embedding": null`; the scaffold computes no embeddings.

Field rules your adapter must satisfy:

- `id` is stable across re-ingestion of the same source item. Your adapter defines its identity mapping; the scaffold never rewrites ids.
- `content.ref` must resolve inside `content/` after the write (checksum and byte count recorded).
- `metadata` is the query surface: `topics`, `tags`, `language`, `license`.
- `retrieved` is null when you cannot prove retrieval time. Your adapter's output carries your own provenance; the scaffold never invents timestamps.

## What the CLI does

```
python3 scripts/protean-context/bootstrap.py ingest --target {TARGET} --adapter <file> --source <path>
```

- Imports only the file you passed by path, and calls `collect(<path>)`.
- Validates every yielded record against `arif-record-v1`. Fail closed: any invalid record aborts the run with exit 2 and writes nothing, all-or-nothing per invocation.
- Writes records under `{TARGET}/arif/records/` and blobs under `{TARGET}/arif/content/`, and appends nothing outside `{TARGET}/arif/`.
- `--dry-run` prints the plan and writes nothing. `--offline` is accepted.

## What the scaffold never does

The locked negative contract, verbatim: no default source paths; no scanning of `{HOME}`, `{HERMES_HOME}`, caches, profiles, or any live tree; no network access; no embedding computation; no credential access; no import of any adapter not explicitly passed by path; no background processes.

## Embedding configuration slot

The `embedding` object in `{TARGET}/arif/arif.json` is the slot:

- Default: `enabled` false, with `provider`, `model`, and `dimensions` null, and `field` set to `embedding`.
- While disabled, the schema gate asserts that no record carries a non-null `embedding` and that `index/` is empty.
- Enabling it is your edit to `arif.json` plus whatever your adapter does. `provider` and `model` values are your configuration, not scaffold defaults. The scaffold provides the slot and the record field, computes nothing, and downloads nothing.

External storage engines sit behind this same boundary as user-side upgrades: your adapter and your configuration, never a dependency of this scaffold.
