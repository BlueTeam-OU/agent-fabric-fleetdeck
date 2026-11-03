---
role: "rust-ui-dev"
class: solution
topic: "j180-account-list-cadence"
description: "j180 FleetDeck: moveto --list read every 60 s (ACCOUNT_LIST_REFRESH_S), map stays 10 s; PR #52; unbound-account retries had kept the list at 10 s"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-31"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - cda49158450888be
---

## j180 FleetDeck: moveto --list read every 60 s (ACCOUNT_LIST_REFRESH_S), map stays 10 s; PR #52; unbound-account retries had kept the list at 10 s

j180 (2026-10-30) delivers fabric-coordinator's yes (REPLY 01a18ec3, seq 679915) to read the account list less often. It is PR #52 on BlueTeam-OU/agent-fabric-fleetdeck, commit d8c9a3da, branch develop-qzapp/rust-ui-dev-01/feat/j180-yes-to-the-60-s-account.

- `ACCOUNT_LIST_REFRESH_S = 60` sits beside `PANE_MAP_REFRESH_S = 10`. `Deck._listed(now)` returns the cached `account_list` until it is a period old. `_accounts(now)` reads fresh and stores the result plus `listed_at`.
- Non-obvious: `_restore(only=retry)` used to read `moveto --list` itself. An UNBOUND account stays in `retry` and is retried at every map read, so one unbound account kept the list read at 10 s. A retry now uses `_listed`; only a whole restore reads fresh.
- A failed read leaves `listed_at` where it was, so the next map read tries again.
- Tests that change `h.logins` or `h.roles` must follow to `ACCOUNT_LIST_REFRESH_S`, not `PANE_MAP_REFRESH_S`. The tab map is also read at the first follow after restore (mapped_at None), which is pre-existing.
- Auto mode refused reading the owner's deck /proc stat (pid of ~/projects/herdr/fleet-deck/fabric-deck). Before/after CPU is for the owner to run: A scratch path <pid> 30 3.

2026-10-30 ~22:15: #52 MERGED at d0e35861 (1 work, 1 fix; minimum 1). Review round 1 found F1: with an account in retry, a failed list read was read again by the retry in the same look, and its failure set `lost`. Fixed with `list_failed_at` (the list is read at most once per look; a look is identified by its `now`), and a retry whose read fails returns without setting `lost`. Round 2 found F1 fixed and nothing new. REPLY 01a18edc (seq 680562) was sent to fabric-coordinator. The CPU before/after is the only acceptance item left open; post the numbers on #52 when the owner has them.

*Anchors: `fleet-deck/fabric_deck.py::ACCOUNT_LIST_REFRESH_S`, `fleet-deck/fabric_deck.py::_listed`*

*Observed 2026-10-30 (rust-ui-dev)*
