---
role: "rust-ui-dev"
class: workflow
topic: "fabric-review-next-chain"
description: "fabric-review next: feed it the previous round's generated request json, not the original yaml, or the round number and range go wrong"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-31"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 8017f945c8e7bd72
---

## fabric-review next: feed it the previous round's generated request json, not the original yaml, or the round number and range go wrong

`fabric-review next REQUEST --pr N --head SHA` derives round N+1 from REQUEST.
- REQUEST must be the json that the previous `next` (or `brief`) run wrote (`<name>-rrK.json` beside it), carrying `review_round`.
- Re-feeding the original review-mode yaml renders the same round number again (two "round 2" briefs on PR #50, 2026-10-28). Its range is also refused, as not starting at the last review's head.
- To change the objective, requirements or compatibility for the next round, edit the fields in that json, then run `next` again. Check `review_round` and `## Range` in the output before dispatching.
- A base that is not on the default branch needs `card_base` (the first round's base).

**Why:** a wrong round number posts a review the gate counts under the wrong round. A stale objective made the reviewer judge against text the fix had already superseded.
**How to apply:** after every `next`, grep the brief for `"review_round"`, `## Range` and `## Objective` before dispatching. Related: [[review-tools-bound-to-clone]]

*References: review-tools-bound-to-clone*

*Observed 2026-10-28 (rust-ui-dev)*
