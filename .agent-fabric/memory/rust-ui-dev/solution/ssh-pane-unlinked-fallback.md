---
role: "rust-ui-dev"
class: solution
topic: "ssh-pane-unlinked-fallback"
description: "Why an ssh harness pane with no ssh_client link still reads RUNNING: the sole-pane fallback (j19, PR #35) and its refusals"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - cc95e3cfcfbaedd5
---

## Why an ssh harness pane with no ssh_client link still reads RUNNING: the sole-pane fallback (j19, PR #35) and its refusals

FleetDeck PR #35 (merged 2026-10-15 as 0e5a444e; j19, request 01a14152 from the operator, 2026-10-15): panes whose ssh connected
before enter-ssh recorded `ssh_client` (c3e476c2) have no link in State; after a controller restart
every account read "running elsewhere". Fallback in `ssh_harness` (fleet-deck/fabric_deck.py):
the pane carries the session when `sole_pane` (login not in `Deck.shared`: no second tab with the
login's label, counted as `AccountTab.others` by `Herdr.account_tabs`), `not live.linked` (no
session of the record, live or over, carries ssh_client; `Live.linked` in deck_tabs.py) and
`live.count == 1`. Any of those failing keeps #32's endpoint match.
- "Linked" counts ended sessions too: the pane's own endpoint on a gone session means the live
  one is someone else's (existing test kept that case running elsewhere).
- Extends [[ssh-pane-endpoint-match]]. The operator restarts the controller and reads the dots
  back after the merge; agents never touch the live deck.
- Review round 1 caught fleet-deck/README.md still teaching the old rule: a behaviour change to ssh_harness needs the README ssh-pane bullets updated in the same commit.

*References: ssh-pane-endpoint-match*

*Anchors: `fleet-deck/fabric_deck.py::ssh_harness`, `fleet-deck/deck_tabs.py::Live`, `fleet-deck/fabric_deck.py::account_tabs`*

*Observed 2026-10-15 (rust-ui-dev)*
