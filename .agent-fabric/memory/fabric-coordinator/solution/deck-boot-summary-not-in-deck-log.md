---
role: "fabric-coordinator"
class: solution
topic: "deck-boot-summary-not-in-deck-log"
description: "fleet-deck start --auto prints its \"up: N; skipped\" boot summary to its own terminal, not deck.log; use presence instead"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: user
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 78dcc979954c16c6
---

## fleet-deck start --auto prints its "up: N; skipped" boot summary to its own terminal, not deck.log; use presence instead

`fleet-deck start --auto` prints its boot summary (`up: N; skipped: …; not up yet: …`) with `say()` to the terminal it runs in (`fleet-deck/fleet_deck.py` `boot_fleet`). It is not written to `~/.local/state/fabric-deck/deck.log`, which holds only the controller's state lines. If the owner's terminal is gone, `fabric-ctl all presence` "since" times show when the boot ended (2026-10-31: 22:41–22:48Z for 29 accounts, j508).

In attach mode with `[fleet_deck] tabs = "all"` (#56), the deck keeps one `ssh … -- attach` per account. A killed attach ssh is restarted at once, with no refocus. The session in the unit keeps running (kill test on python-dev-02, 2026-11-01 08:40:49Z). See [[harness-pane-enter-lost-at-start]].

*References: harness-pane-enter-lost-at-start*

*Anchors: `fleet-deck/fleet_deck.py::boot_fleet`*

*Observed 2026-11-01 (fabric-coordinator)*
