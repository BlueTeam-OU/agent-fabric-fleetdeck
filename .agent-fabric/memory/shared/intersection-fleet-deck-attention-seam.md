---
role: shared
class: intersection
topic: "fleet-deck-attention-seam"
description: "FleetDeck's \"needs you\" views read agent-fabric fleet.py's derived `attention` section — who owns which half of the seam, and where its shape is authoritative"
tier: 2
knowledge_scope: full
shared_with:
  - "python-dev"
  - "rust-ui-dev"
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 0c1503aa0e941c74
---

## FleetDeck's "needs you" views read agent-fabric fleet.py's derived `attention` section — who owns which half of the seam, and where its shape is authoritative

The seam between agent-fabric's `tools/fabric/fleet.py` (python-dev's; python-dev-01 built it)
and FleetDeck's needs-you views (rust-ui-dev's; agreed with rust-ui-dev-01 on j55, REPLY
01a125e1-8be8, 2026-10-10) has landed on both sides (checked 2026-10-12 on agent-fabric
origin/main and agent-fabric-fleetdeck origin/master).

- **Producer, authoritative shape:** fleet.py's ATTENTION docstring and `attention_data` /
  `attention_record`. A section derived from `states` + `jobs`, with no source or cache of
  its own. data = {level needs_input|waiting|none, reason, since, blocked, pending,
  context_pct, context_at, output}. needs_input wins over waiting. reason is
  "permission"/"question" (or null) for needs_input, and the job's `blocked_on` for waiting:
  the agent's own words flattened, cut at 80, NOT scrubbed. A failed or unknown input is
  failed, never `none`.
- **Consumer, authoritative behaviour:** fleet-deck/README.md "Needs you". It reads the
  section with fleet.py's own reader from records the deck already holds, never as a
  separate fetch. Only needs_input and an owner-blocked job count in "n of N need you".
- **The rule both halves keep:** reason is shown as plain text only, never as a link or a
  command.

**Why:** the 2026-10-10 agreement predates s3 (context_pct/output, reason values).
The code is the record now, not this note.
**How to apply:** to change the shape, change fleet.py and the deck's README together.
That needs python-dev's agreement, because neither half changes alone.

*Observed 2026-10-12 (rust-ui-dev)*
