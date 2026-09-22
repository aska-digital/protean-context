# modules/ of {ELDUNARI_NAME}

This directory holds the payload of this Eldunari: markdown modules, one fact one home. It ships empty except for this stub.

One fact, one home. A fact lives in exactly one module; every other mention is a pointer (relative path) to it. A pointer that does not resolve is a defect.

Rules for this directory:

- Payload lives here: project facts, procedures, history, and configuration values, as markdown files whose names you choose.
- `ROUTER.md` stays router-only: identity, hard rules, and pointers. When a fact belongs here, put it in one module and leave a pointer in `ROUTER.md`.
- Every mention of a fact outside its home module is a pointer (relative path), never a copy.
- Markdown only. No code, no binaries, no bundled external corpus.
