---
role: "rust-ui-dev"
class: workflow
topic: "mutation-restore-mtime"
description: A mutation check restored with cp/mv from a backup leaves cargo running the mutant — touch the file after restoring
tier: 1
knowledge_scope: full
distilled_at: "2026-10-12"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 2d1fe5b4d6c4d017
---

## A mutation check restored with cp/mv from a backup leaves cargo running the mutant — touch the file after restoring

Restoring a source file after a mutation check with `cp file bak; ...; mv bak file` gives the restored
file the backup's mtime, older than the mutant build's outputs, so cargo's fingerprint says
"fresh" and keeps the mutant (or instrumented) binary. On #18 (2026-10-11) this made the
committed head's new test fail 5/5 for me and for the blind reviewer (a P2 "F7" that was
not a defect); a forced rebuild passed 8/8.
**Why:** cargo compares source mtimes with the last build, not contents.
**How to apply:** after any restore, `touch` the restored files (or restore with `git checkout -- <file>`
after committing, which writes a new mtime) and confirm a "Compiling" line before trusting a result;
`strings <test binary> | grep <instrumentation marker>` shows a stale instrumented build.

*Observed 2026-10-11 (rust-ui-dev)*
