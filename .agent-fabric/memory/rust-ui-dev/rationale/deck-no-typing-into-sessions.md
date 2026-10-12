---
role: "rust-ui-dev"
class: rationale
topic: "deck-no-typing-into-sessions"
description: "Why the Fleet Deck flags an agent with no inbox watch on the board instead of typing a re-arm prompt into its session"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-12"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 20eae35e6204da99
---

## Why the Fleet Deck flags an agent with no inbox watch on the board instead of typing a re-arm prompt into its session

2026-10-11, j5 (fabric-coordinator REQUEST 01a12a7c): the deck was asked to type a fixed
"start your inbox watch" prompt into idle agents' Claude sessions. The remit forbade agent-to-agent
prompting; fabric-coordinator added a bounded exception (fleetdeck #22). Claude Code's auto-mode
classifier then denied building it as "instruction poisoning". The owner narrowed it, and left the
choice to rust-ui-dev-02's judgement: the board flags the agent ("inbox off 3m", fleetdeck #24),
nothing is typed. Reasons: typing into another agent's live session is the channel both the
remit and the classifier guard; a flag lets the person wake it; fabric-coordinator's Stop hook
re-arms the watch at turn ends. The fact comes from fleet.py's proc `inbox_watch`
(REQUEST 01a12b2e, python-dev-01), not a pgrep in the view (ADR-046; one host only).
**How to apply:** do not revive the typing re-arm without a new owner decision; #22's exception
is unused.

*Observed 2026-10-11 (rust-ui-dev)*
