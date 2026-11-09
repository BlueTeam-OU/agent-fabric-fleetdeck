---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-attach-facts"
description: "Measured facts about FleetDeck's terminal attach, the nested guard, headless servers and the deck's typing lock, from j167 part 2"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - f479c2305f6b8f26
---

## Measured facts about FleetDeck's terminal attach, the nested guard, headless servers and the deck's typing lock, from j167 part 2

- **terminal attach** needs a sized pty: 0x0 fails with "terminal reported a zero size". Its detach key is ctrl+b q. Killing the attach leaves the pane's program running (live read-back, agent-fabric docs/live-checks/2026-10-31-fleetdeck-harness-unit.md).
- **Nested guard.** `exit_if_nested_disabled` in src/main.rs covers only the default launch and the hidden `client` mode, so `terminal attach` is not guarded. ssh forwards only COLORTERM, not HERDR_ENV.
- **A headless server** with no startup cwd and nothing restored opens no workspace, so a unit's pane needs a step after start.
- **`pane process-info`** takes `--pane <id>` in the fork; a positional pane id exits 2 (agent-fabric#441 fixed harness_pane.py).
- **Typing lock.** Every line the controller or the boot types at an attach-mode harness pane's shell goes under a per-user flock (`harness_lock`, `typed_at_bare_shell`) with a second look; the attach typist holds the lock until the attach runs (up to 5 s). A pane the deck typed a moveto into is not taken as bare for 5 s (`typed_at`). During a boot, the controller leaves accounts that are not up to the boot (`_boot_holds`).
- **Known limits.** Safeguard-stop detection reads the pane's screen, so only while the tab is attached. The controller stamps typed_at with the look's time, before a lock wait. A PrivateTmp unit without /run/user would not share the lock.
- **Release builds poll the fork.** A release server fetches index.toml, 22 agent manifests and latest.json (24 curls) every 30 min and at start; a debug build never does. `[update] version_check = false` and `manifest_check = false` stop it. Measured with a logging curl wrapper on PATH; ps sampling every 250 ms misses them.

*Observed 2026-11-03 (rust-ui-dev)*
