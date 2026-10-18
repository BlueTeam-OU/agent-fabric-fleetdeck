---
role: "rust-ui-dev"
class: solution
topic: "deck-unbound-role-new-workspace"
description: "Why FleetDeck put a new account's tab in workspace New, and why herdr cannot move it afterwards"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 1b281dbfeff512bb
---

## Why FleetDeck put a new account's tab in workspace New, and why herdr cannot move it afterwards

`moveto --list` (agent-fabric tools/fabric/moveto.py role_of) prints `-` for an account
whose role is not bound yet, and lists a new account before its role is bound; the deck's
seed_workspace("-") gave New. herdr's TabMove only reorders within one workspace (src/api/schema/tabs.rs
TabMoveParams: tab_id, insert_index), so a tab made in the wrong workspace stays there.
Fix (agent-fabric-herdr #16, fc189f86): no tab for an UNBOUND account; it is retried at each
map read and made once the role is bound. Found 2026-10-11 from rust-ui-dev-02's own account.

*Observed 2026-10-11 (rust-ui-dev)*
