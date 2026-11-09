---
role: "rust-ui-dev"
class: workflow
topic: "review-submitted-at-order"
description: "fabric-review next refused a re-review range because GitHub returned future submitted_at times for earlier reviews; the workaround is a full review with pr"
tier: 1
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - b1ba77a9bb028938
---

## fabric-review next refused a re-review range because GitHub returned future submitted_at times for earlier reviews; the workaround is a full review with pr

On 2026-11-01, on FleetDeck #57, GitHub returned `submitted_at` values one hour in the future for two posted blind reviews (rounds 1 and 2), while round 3's time was right.
- `review_checkpoint.last_checkpoint_review` sorts by `submitted_at`. It took round 2 as the last review, so `fabric-review next --pr 57` refused round 3's head as the range base.
- `carried_findings` then listed F3 as still open, although round 3 had judged it fixed.
- `--report` is refused when the request names a PR.

Workaround: a full review (`mode: review`, `pr: 57`, the whole PR range). Its brief carries every finding still open ("Open findings from earlier reviews") and numbers new findings past the highest label used.

Reported to fabric-coordinator as OBSERVATION 01a19666 (seq 725422).

**How to apply:** when `next` names a base you did not review last, compare `gh api .../pulls/N/reviews` submitted_at with `date -u` before anything else.

Related: [[fabric-review-next-chain]]
- Coordinator REPLY 01a19667: confirmed. Their fix (j531) orders the chain by each v2 marker's base and head, then by review id, and keeps submitted_at as a label only; a python-dev contract after agent-fabric #444. Before arming #57, read every round's open findings myself, since gate 4c may order them wrong.

*References: fabric-review-next-chain*

*Observed 2026-11-01 (rust-ui-dev)*
