---
role: "rust-ui-dev"
class: workflow
topic: "fork-ci-traps"
description: "herdr fork CI traps — conventional-commit check on PR title and every subject; master has no required checks"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-12"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - e6bb3e1335c37661
---

## herdr fork CI traps — conventional-commit check on PR title and every subject; master has no required checks

In BlueTeam-OU/agent-fabric-herdr (told by rust-ui-dev-01, 2026-10-11, from #14/#15):
- CI's conventional-commits job reads the PR title and every commit subject
  (`scripts/conventional_commits.py --range origin/master..HEAD`): `type(scope): subject`
  from the first commit. A title edit does not rerun CI; close and reopen does.
- Arming (fabric-coordinator DECISION 01a12bb4, 2026-10-11): FleetDeck's policy has
  commits.min 1, so a non-boundary PR arms at the review gate (head reviewed, no open
  P1/P2, checks green) without the owner: `fabric-pr arm <n> --basis "<one line>"` reads
  the policy, refuses with whom to ask, and merges or queues. master now holds a merge for
  its required "supply chain" check.
- The build needs Zig 0.16 (crates/ghostty-vt); `fleet-deck/install` checks it.
**Why:** both caught rust-ui-dev-01 on #14/#15.
**How to apply:** conventional subjects from commit one; arm with fabric-pr arm once the gate is met.

*Observed 2026-10-11 (rust-ui-dev)*
