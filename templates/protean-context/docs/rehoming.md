# Re-homing and configuration

This guide ships with the ingredient at `templates/protean-context/docs/rehoming.md`. It follows the re-homing convention of this ecosystem: example paths are clearly marked `EXAMPLE`, exactly one environment override exists, and all state is relative to the bundle.

## 1. Where things live

Token table:

| Token | What it is |
|---|---|
| `{HERMES_HOME}` | Hermes home. Default `{HOME}/.hermes`. Overridable once, via the `HERMES_HOME` environment variable (section 2). |
| `{HERMES_HOME}/profiles/{PROFILE_NAME}/` | Hermes profile layout: per-profile `SOUL.md`, `config.yaml`, `skills/`, `memories/`, `cron/`, and related profile files. |
| `{TARGET}` | The scaffold target you chose when you ran `init`. Everything this scaffold creates lives under `{TARGET}`. |

No other roots exist. Never write an absolute home path into configuration, scripts, or docs; use these tokens. Credentials appear as key names only, `.env.EXAMPLE` style; values never ship.

## 2. The `HERMES_HOME` override

Exactly one environment variable overrides the home root in this version. Set it before running any command that must resolve a different home. There is no second override.

`EXAMPLE` (illustrative only, not a default):

```
export HERMES_HOME={HOME}/example-hermes-home
```

Everything under `{HERMES_HOME}` resolves from that value, including the profile layout from section 1.

## 3. Linking an Eldunari to a Hermes profile

`ROUTER.md` may contain identity, hard rules, and pointers only. When a fact lives in a Hermes profile, the pointer references the profile path with the `{PROFILE_NAME}` token and the file stays where it is. Profile files are never copied into `modules/`.

One fact, one home. A fact lives in exactly one module; every other mention is a pointer (relative path) to it. A pointer that does not resolve is a defect.

`EXAMPLE` pointer target (clearly marked, not a default path):

```
{HERMES_HOME}/profiles/{PROFILE_NAME}/skills/
```

Referenced in place, never duplicated into the tree. The profile's `memories/` directory is user data: it is never part of any distribution, never copied by the scaffold, and never read by `init`.

## 4. Arif store and index configuration

All Arif storage configuration lives in one file: `{TARGET}/arif/arif.json` (schema `arif-store-v1`, `schemaVersion` 1).

- `store`: `kind` is `file-v1`, the default in this version. `recordsDir` (`records`) and `contentDir` (`content`) are relative to `{TARGET}/arif/`. Records are one JSON file each, metadata first; content is stored once, addressed by sha256.
- `index`: `kind` is `none`, `dir` is `index`. The index directory ships empty and is rebuildable from `records/` and `content/` at any time; nothing depends on it.
- `embedding`: `enabled` is false, with `provider`, `model`, and `dimensions` null. Enable it by editing this file, then do whatever adapter work you need; the scaffold computes nothing.

Upgrade path: external engines (for example pgvector or chroma) are user-side adapters behind the ingestion and store boundary. You configure them on your side of that boundary; they are never dependencies of this scaffold, which bundles no database, no server, and no index.

## 5. Hermes settings

Change profile settings with the Hermes CLI only:

`EXAMPLE` (keys only; this guide ships no values):

```
hermes -p {PROFILE_NAME} config set <key> <value>
```

- Never hand-edit `config.yaml`; the CLI validates keys.
- Always pass `-p {PROFILE_NAME}`. A bare `hermes config set` writes the default profile instead of the one you meant.
- Key names only: this guide ships no configuration values and no credential values.

Warning, evidenced: `config set` strips every comment from `config.yaml` when it writes. Back the file up before your first change; comments are not preserved.

## 6. Backup

The whole `{TARGET}` is the state. Nothing this scaffold manages is written outside `{TARGET}`; the no-live-state gate proves it on every run. Copy the directory.

`EXAMPLE` (illustrative destination):

```
cp -R {TARGET} {HOME}/example-backup
```

Back up `{HERMES_HOME}/profiles/{PROFILE_NAME}/config.yaml` separately before any `config set`, per section 5.

## 7. Upgrade and removal

Upgrade: update your installed scaffold copy, then rerun `init` with your names. Schema versions are compared first.

- A scaffold-owned file that still matches its init-receipt hash may be replaced; the old copy is kept under `{TARGET}/.protean-backup/<from>-to-<to>/` first.
- A file you modified is never touched; it is reported and skipped.
- A migration is forward-only, registered as a pair (`n` to `n+1`), and additive: new fields get defaults, existing values are preserved. A migration that would edit user-authored content fails closed and reports the manual step instead.
- A target `schemaVersion` newer than the template is refused with exit 2. Downgrade is never attempted. The receipt records applied migrations.

Removal: `remove` deletes exactly the receipt-listed paths whose current hash still matches.

- A receipt-listed path whose hash differs (you modified it) is skipped and reported.
- Unlisted files are never touched.
- Directories are removed only when empty; the receipt is deleted last.
- `remove --dry-run` prints the same plan without deleting.

Backup note for removal: removal is scoped to the init receipt, so a backup copy of `{TARGET}` (section 6) is still the simplest safety net.

Engine: Hermes by Nous Research, MIT license. This is not a fork; we build on top of it.
