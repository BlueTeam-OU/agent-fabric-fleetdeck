---
role: "rust-ui-dev"
class: workflow
topic: "mutation-restore-mtime"
description: A mutation check restored from a backup leaves cargo (stale mtime) or Python (stale .pyc, same size and second) running the mutant
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 28cdfae41a477a1d
  - 2d1fe5b4d6c4d017
---

## A mutation check restored from a backup leaves cargo (stale mtime) or Python (stale .pyc, same size and second) running the mutant

Restoring a source file after a mutation check with `cp file bak; ...; mv bak file` gives the restored
file the backup's mtime, older than the mutant build's outputs, so cargo's fingerprint says
"fresh" and keeps the mutant (or instrumented) binary. On #18 (2026-10-11) this made the
committed head's new test fail 5/5 for me and for the blind reviewer (a P2 "F7" that was
not a defect); a forced rebuild passed 8/8.
**Why:** cargo compares source mtimes with the last build, not contents.
**How to apply:** after any restore, `touch` the restored files (or restore with `git checkout -- <file>`
after committing, which writes a new mtime) and confirm a "Compiling" line before trusting a result;
`strings <test binary> | grep <instrumentation marker>` shows a stale instrumented build.

**Python has the same trap, and touch does not fix it** (j15, PR #33, 2026-10-15). A `.pyc` is
validated by the source's mtime in whole seconds and its size. A mutant that only reorders
lines has the same size as the original, and a restore in the same second keeps the same
mtime. So `cp bak file; touch file` still ran the mutant's bytecode, and a correct test
failed. Run a mutation loop with `python3 -B`, or `rm -rf __pycache__` after restoring.

*Observed 2026-10-15 (rust-ui-dev)*
