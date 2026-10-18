---
role: "rust-ui-dev"
class: workflow
topic: "codex-review-gateway"
description: "How the second review engine (Codex) runs from this login, how review rounds are posted so the gate stays honest, and how a re-review brief is derived"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - b18cd1a923692314
---

## How the second review engine (Codex) runs from this login, how review rounds are posted so the gate stays honest, and how a re-review brief is derived

- `fabric-review --engine codex <PR> <request.yaml> --gateway chatgpt` with `GH_REPO=` set to the
  fork. Without `--gateway chatgpt` it refuses (no AGENT_FABRIC_CODEX_BASE_URL/KEY on this login).
  It posts its own review in about 5 to 10 minutes. The request's `range` must end at the PR head.
- FleetDeck's arming policy requires both engines on the head (fabric-pr gate shows `claude ✓ codex ✓`).
- Post a Claude round with `fabric-pr post-review` BEFORE pushing its fixes, or it is recorded
  against the new head. A devex-tooling fix is pending: OBSERVATION 01a14011.
- #33 (j15) took 15 Claude rounds and 13 Codex runs. Codex kept finding new races in the same
  class each round (focus during view startup, overlay identity, shell typing). Bring the owner a
  "fix first or arm now" choice as soon as a round finds only that class again.
- **A re-review brief from `fabric-review next`** (j17, #34, 2026-10-15) refuses when round 1's
  `range` starts at a ref name (`origin/master..<sha>`): "the first round's card cannot be
  recovered". Add `card_base: <round 1's base_sha from its dispatch header>` to the request
  and run `fabric-review next <req> --report <round-1 report> --head <new head>` again. Codex
  needs its own request whose `range` ends at the new head (`origin/master..<new head>`).
- **A judgement of a Codex finding (mode finding-adjudication) is a round too**: post it with `fabric-pr
  post-review` before pushing its fixes. Pushed first (j18, #36, 2026-10-16): post it as a plain
  `gh pr comment` saying which head it judged, never as a review, which would cover the new head.
- #37 (2026-10-16): 8 Codex runs, each finding a distinct real edge until round 5 came back clean; a fresh piece of work
  on the same PR (j22) restarts the cycle. A re-review brief from `fabric-review next` holds only the Claude report:
  name the Codex finding in the dispatch prompt so the reviewer knows what the fix answers. A new-work commit on an
  open PR gets a fresh `review` request with `card_base: <first round's base>` (base not on master otherwise refused).
- **Exit 101 with no output** (#39, 2026-10-17): `fabric-review --engine codex` failed twice
  in a row ("codex exited 101: (no output)", nothing posted; `codex --version` fine, 0.162.1),
  then the third run, with a fresh request whose range ended at a newer head, posted normally.
  Retry before reporting; report to fabric-coordinator if it repeats across PRs.
- **#40 (2026-10-17): offer the owner the choice at round 3, not 5.** Codex found a timing edge of
  the same "which harness owns this record" logic every round; rounds 3-5 traded a lost red against
  a false red. When I asked, I described both round-4 findings as fail-safe; the judgement found one
  painted a false red (P2), so I fixed it before arming. Have the findings judged BEFORE framing the
  owner's choice, and state each one's fail direction from the judgement, not my own read.

*Observed 2026-10-17 (rust-ui-dev)*
