---
role: "rust-ui-dev"
class: solution
topic: "fake-herdr-rearms"
description: "fleet-deck FakeHerdr — a pane re-arms \"moveto --wait\" one settle after any run; assert a restore's decision by the runs since, not by counts"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 8b051f8a1a6fd1ce
---

## fleet-deck FakeHerdr — a pane re-arms "moveto --wait" one settle after any run; assert a restore's decision by the runs since, not by counts

In fleet-deck/test_fabric_deck.py, FakeHerdr does not put the harness pane's
foreground into moveto after a run, so the deck re-arms `moveto <a> --wait`
RESTORE_SETTLE_S after every decision (seen with and without a boot, 2026-10-13).
Counting "--wait" runs across a longer follow is therefore fragile. To assert what
one restore decided, slice `h.herdr.runs()` from before the restore and follow only
to start + 1 + RESTORE_SETTLE_S; a simulated herdr restart is one poll with
`h.herdr.down = True` (helper `Restore.restart_herdr`, PR #30).

*Observed 2026-10-13 (rust-ui-dev)*
