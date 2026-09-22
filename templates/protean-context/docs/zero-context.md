# Zero-context recovery: operator and agent guide

Zero-context recovery is the pattern this scaffold implements. A fresh agent
rebuilds working context from disk on every entry: the registry names each
Eldunari, one router file narrows the task to one module, and one module
carries the facts. The scaffold ships the empty shape. The operator supplies
the facts.

## The cold-start loop

1. Read the registry at `{TARGET}/eldunarya/eldunarya.json` and resolve the
   task's Eldunari name to its router path.
2. Read exactly one `ROUTER.md`. Read nothing under `modules/` yet.
3. Resolve exactly one pointer of the form `modules/<file>.md` for the task.
4. Read exactly one module file. Never load all modules.
5. If a pointer does not resolve, stop and report the defect instead of
   guessing.

## The write discipline

One fact gets one home module. The writer places the fact in exactly one
markdown file directly under `modules/`, then records one pointer line per
target in `ROUTER.md` in the form `modules/<file>.md -> what lives there`.
The writer adds the line when a module is added and deletes the line when
the module is gone.

## The pointer rules

Every mention of a fact outside its home module is a relative pointer, never
a copy. A pointer without a home is a defect. A pointer that does not resolve
is a defect. Pointers to Hermes profile files reference the profile path with
the `{PROFILE_NAME}` token under `{HERMES_HOME}` and never copy profile files
into `modules/`.

## How to verify by read-back

After writing, the writer reads the file back from disk and confirms the
bytes match the intent. After changing pointers, the writer confirms each
`modules/<file>.md` line in `ROUTER.md` names a file that exists. The
`verify` command checks scaffold shape; pointer resolution is the writer's
duty on every edit.

## What the scaffold will not do

The scaffold bundles no facts, no recovery dumps, and no content migration.
It computes no embeddings, keeps no index, and reads nothing outside
`{TARGET}` except the explicit source passed to ingestion. It never proves
that a user fact is true. It proves shape and resolution only.

## Worked synthetic example

An Eldunari named `demo` holds one fact in `example-module.md`. The registry
entry for `demo` points at its router. The router carries one line:

```
modules/example-module.md -> the demo fact
```

The entering agent reads the registry, then the router, then
`modules/example-module.md`, and stops. Three reads, one fact, no search.

Engine: Hermes by Nous Research, MIT license. This is not a fork; we build
on top of it.
