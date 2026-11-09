---
role: "fabric-coordinator"
class: workflow
topic: "review-next-needs-card-base"
description: "fabric-review next refuses a round-1 request whose range base is a ref name (origin/master) until card_base is set"
tier: 1
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: user
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - c288ba867955d887
---

## fabric-review next refuses a round-1 request whose range base is a ref name (origin/master) until card_base is set

`fabric-review next <request> --report <r1> --head <sha>` refuses when the round-1 request's
`range:` starts with a ref name such as `origin/master..<sha>`: "the range's base 'origin/master'
is not a commit id, so the first round's card cannot be recovered". The fix is to add
`card_base: <base_sha from round 1's dispatch header>` to the request and run it again.
Seen on herdr PR #55 (BlueTeam-OU/agent-fabric-fleetdeck), 2026-10-31.

**Why:** `next` derives the re-review card from the round-1 base, and a ref has moved by then.
**How to apply:** write a round-1 request's range with the base sha, or set `card_base` up front.

*Anchors: `agent-fabric:tools/fabric/review_rounds.py::card_base`*

*Observed 2026-10-31 (fabric-coordinator)*
