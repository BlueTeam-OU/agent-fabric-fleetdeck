---
role: "rust-ui-dev"
class: workflow
topic: "agent-survived-kill-check"
description: "How to show from my own account that another account's agent session survived a kill of the deck's attach: presence start time plus the states row"
tier: 1
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - df410666ac76dc15
---

## How to show from my own account that another account's agent session survived a kill of the deck's attach: presence start time plus the states row

To check that killing a deck pane's attach (`ssh … -- attach`) left an account's agent running, without reading that account's processes (auto mode refuses `ps -u`, `/proc` and its cgroup):
- `fabric-ctl <login> presence` gives the running session's start time. A time before the kill means the same session lived through it.
- `fabric-ctl <login> states --json` gives the current row: session id, state, `since` and `ts`. It keeps no history. A fresh `ts` with that session id means the state stream still reports it.

Used for j167 step 6 on 2026-11-01: python-dev-02 had been running since 07:34:02Z, the attach was killed at 08:40:49Z, and the states row was still fresh at 10:02Z. The figure is in FleetDeck #58's body.

Related: [[j167-fleetdeck-focus-baseline]], [[herdr-restart-loses-moveto-agents]]

*References: herdr-restart-loses-moveto-agents, j167-fleetdeck-focus-baseline*

*Observed 2026-11-01 (rust-ui-dev)*
