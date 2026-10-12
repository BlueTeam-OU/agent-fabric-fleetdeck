---
role: "rust-ui-dev"
class: solution
topic: "herdr-fork-baseline"
description: "Where the herdr fork began: upstream 3d9d2b18 (master 2026-10-06, version 0.9.3 = v0.9.3 + 46 unreleased commits); Herdr stable tags are side commits, never ancestors of master"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-12"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 56f42ba385776d6c
---

## Where the herdr fork began: upstream 3d9d2b18 (master 2026-10-06, version 0.9.3 = v0.9.3 + 46 unreleased commits); Herdr stable tags are side commits, never ancestors of master

The fork point is herdrdev/herdr `3d9d2b18` (master, 2026-10-06), the single parent of the first fork commit, 0bc73518. Cargo.toml there says 0.9.3.

Herdr's stable tags are **not** on master. A stable release is promoted from a preview on a side commit (v0.9.3 = 7b116c05, from preview-2026-09-29-9dc3a1df2b56), and only its metadata is applied back to master (f9a99bd2 "release: synchronize metadata for v0.9.3"). So `git merge-base --is-ancestor v0.9.3 master` is false. `git describe` on the fork point gives preview-2026-09-29-9dc3a1df2b56-46-g3d9d2b18. The fork's merge base with upstream moves with every sync (now 2563803d, after sync merge 3875d7c4 / PR #8), so the merge base is not the fork point.

**Why:** a "which version are we based on" question has a trap. The newest tag, the merge base and the v0.9.3 tag all give the wrong answer.
**How to apply:** cite the fork point, not the tag. The import ledger is docs/fleetdeck/UPSTREAM.md. Origin carries Herdr's v*/preview-* tags (157 refs), so never treat a v* tag as FleetDeck's without checking that its Cargo package is agent-fabric-fleetdeck. See [[fleetdeck-identity]].

*References: fleetdeck-identity*

*Observed 2026-10-10 (rust-ui-dev)*
