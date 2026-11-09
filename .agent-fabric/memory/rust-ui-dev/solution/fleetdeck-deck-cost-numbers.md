---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-deck-cost-numbers"
description: "What the FleetDeck deck cost before and after j167's focus-only panes, and how to measure it on this host (what auto mode refuses)"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - e543f4c0d0ae7bcb
---

## What the FleetDeck deck cost before and after j167's focus-only panes, and how to measure it on this host (what auto mode refuses)

Numbers (29 accounts):
- Before, 2026-10-26: 86 deck ssh (29 --wait, 29 --watch, 28 shell); 30 fabric_view processes ~79% CPU together, ~2-3% each idle; account side 30 watch.py ~3.8% each.
- After j167 part 1 (#49), 2026-10-27: 31 deck ssh (29 --wait, 1 --watch, 1 shell); views ~5%; one --watch on the account side. The operator's cgroup stayed ~120%: the controller cost ~33%, nearly all `moveto --list` every 10 s (a sudo per account), which j180 moved to 60 s ([[j180-account-list-cadence]]).
- After part 2 with `tabs = "all"`, 2026-11-01: 29 ssh `-- attach`, 29 --watch, 0 --wait; user-1000 cgroup 99-136% over six 10 s samples (the before window had other load, so not a clean compare).

Measuring:
- Count deck ssh with `ps`, but filter out your own claude process: its argv carries the request text and matches `ssh -i .*fabric_deck`.
- CPU from /proc/<pid>/stat utime+stime (fields 14-15) for the process itself; fields 16-17 count only reaped children. Take six 10 s cgroup samples: one can spike (826% seen).
- Auto mode refuses reading the `user` login's processes, /proc entries, deck log and cgroup: ask fabric-coordinator for those numbers instead of retrying.

*References: j180-account-list-cadence*

*Observed 2026-11-03 (rust-ui-dev)*
