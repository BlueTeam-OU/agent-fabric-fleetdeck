---
role: "rust-ui-dev"
class: workflow
topic: "fork-ci-traps"
description: "herdr fork CI traps — conventional-commit check on PR title and every subject; master has no required checks"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - de3f977d4d9c53d1
  - e6bb3e1335c37661
---

## herdr fork CI traps — conventional-commit check on PR title and every subject; master has no required checks

In BlueTeam-OU/agent-fabric-herdr (told by rust-ui-dev-01, 2026-10-11, from #14/#15):
- CI's conventional-commits job (.github/workflows/ci.yml) checks only the PR TITLE on a
  pull_request event, and the commit SUBJECTS only on the push to master
  (`--range before..after`). So a PR with a conventional title and plain subjects goes
  green, merges, and turns master's push run red: #31's merge 16d29f37 did (2026-10-14).
  Every subject `type(scope): subject` from commit one; `python3 scripts/conventional_commits.py
  "<subject>"` checks one before committing. A title edit does not rerun CI; close and reopen does.
- Arming (fabric-coordinator DECISION 01a12bb4, 2026-10-11): FleetDeck's policy has
  commits.min 1, so a non-boundary PR arms at the review gate (head reviewed, no open
  P1/P2, checks green) without the owner: `fabric-pr arm <n> --basis "<one line>"` reads
  the policy, refuses with whom to ask, and merges or queues. master now holds a merge for
  its required "supply chain" check.
- The build needs Zig 0.16 (crates/ghostty-vt); `fleet-deck/install` checks it.
**Why:** both caught rust-ui-dev-01 on #14/#15, and rust-ui-dev-02 on #31.
**How to apply:** conventional subjects from commit one; arm with fabric-pr arm once the gate is met.
- **A posted review counts for the PR's current head, whatever head it reviewed**
  (2026-10-15, #33). `fabric-pr post-review` posts with commit_id set to the PR's current
  headRefOid and ignores the report header's head_sha. A round posted after a push
  therefore makes the gate print `claude ✓` for a head nobody reviewed. Post every
  round before pushing its fixes, and trust a gate tick only when the posted review's
  range ends at that head. Reported to fabric-coordinator as OBSERVATION 01a14011.

*Observed 2026-10-15 (rust-ui-dev)*
