# ROUTER: {ELDUNARI_NAME}

## Purpose

This file is the hot path of the Eldunari named `{ELDUNARI_NAME}`, created inside the Eldunarya at `{TARGET}/eldunarya` by the bootstrap CLI. It carries identity, hard rules, and pointers only, so that a reader (or an agent) gets the essentials without loading any payload file.

## Entering this Eldunari

The entering agent reads this file first. The load order is the registry,
then this file, then exactly one module. The agent resolves exactly one
pointer per task and never loads all modules. A pointer of the form
`modules/<file>.md` names the single home of the fact it describes. An
unresolvable pointer is a defect: the agent stops and reports it instead of
guessing. This file stays router-only: identity, hard rules, and pointers.
Facts live in `modules/`.

## Rules

- This file holds three kinds of content only: identity (what this Eldunari is for), hard rules (inviolable constraints), and pointers (paths, with what lives there).
- No project facts, no procedures, no history, no configuration values in this file. Payload belongs in `modules/`.
- Point, never copy. A fact mentioned here without a pointer to its home is a defect; a pointer that does not resolve is a defect.
- Keep pointers relative where the target lives under this tree; reference Hermes profile files in place by token path and never copy them into `modules/`.
- When a rule and a module disagree, fix the module or the rule; never fork the fact into a second home.

## Pointers

One line per target, in this form:

```
modules/<file>.md -> what lives there
```

Ship state (no modules yet beyond the stub):

```
modules/README.md -> the one-fact-one-home invariant for this Eldunari's payload
```

Add a line here whenever you add a module under `modules/`, and delete the line when the module is gone. Module file names are your choice; markdown only.
