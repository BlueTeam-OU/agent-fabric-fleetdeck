---
role: "fabric-coordinator"
class: workflow
topic: "deck-live-readback-recipe"
description: how to read back fleet deck attach behaviour live on the operator deck (tab focus, tabs setting, ssh counts) without miscounting
tier: 1
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: user
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - a9bd8eabd14e69e4
---

## how to read back fleet deck attach behaviour live on the operator deck (tab focus, tabs setting, ssh counts) without miscounting

The operator deck runs as login `user`, from the herdr checkout's `fleet-deck/` at master, config `~/.config/agent-fabric-fleetdeck/config.toml` (`[fleet_deck] tabs`), log `~/.local/state/fabric-deck/deck.log`.

- Move focus: `env -u HERDR_SOCKET_PATH -u HERDR_CLIENT_SOCKET_PATH agent-fabric-fleetdeck tab focus <tab_id>` (`tab list` gives ids and which one is focused).
- Count ssh per kind from `pgrep -u user -a ssh | grep fabric_deck` saved to a file first: `pgrep -af '<pattern>'` run from bash matches its own command line, so a count comes out one too high (on 2026-11-01 it read 30 when there were 29).
- The deck re-reads `tabs` at the next map read (about 10 s). Going from "focus" back to "all", it starts the panes one after another: 87 panes took 37 s (j522, herdr #56 at cc7da532).
- Change the live config only with the owner's leave. Back it up first and check the restored copy with `cmp`.

*Anchors: `herdr:fleet-deck/fabric_deck.py::deck_tabs`*

*Observed 2026-11-01 (fabric-coordinator)*
