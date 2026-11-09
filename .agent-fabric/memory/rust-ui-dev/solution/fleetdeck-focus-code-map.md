---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-focus-code-map"
description: "Where the FleetDeck deck's focus rule lives (panes, focus signals, hang-up, views) and the design j167 chose for focus-only tabs and the per-account harness server"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - c161e444b84489e3
---

## Where the FleetDeck deck's focus rule lives (panes, focus signals, hang-up, views) and the design j167 chose for focus-only tabs and the per-account harness server

The deck code is `fleet-deck/` in the FleetDeck fork (BlueTeam-OU/agent-fabric-fleetdeck), read on master.

- **Panes.** `fabric_deck.Deck._restore_account` builds an account tab's harness, shell, status and agent panes. `_arm` types `moveto <login> [--wait|--watch|--attach]` with `pane run`. The ssh itself is agent-fabric's moveto; the deck never builds an `ssh -i`.
- **Focus signals.** herdr emits `tab.focused`, `workspace.focused` and `pane.focused` (socket `events.subscribe` or a plugin `[[events]]` hook), and no "lost" event: a loss is the next tab.focused. DECSET 1004 reaches only a tab's focused pane. The deck reads focus at each look from `workspace list` (the focused workspace's `active_tab_id`) in `_follow_focus`.
- **Pause.** `_pause` hangs up a pane's foreground pgid (`hang_up_group`, SIGHUP as closing the pane would) and re-queues it. The `ending` set covers focus coming back before the hang-up lands. `[fleet_deck] tabs = "all"` (#56) turns the rule off. See [[j188-deck-tabs-setting]].
- **Views.** fabric_view's agent pane fetches only when focused (`Refresher.lazy`) and rests unfocused: no tick, no render.
- **Stop and boot.** `boot.hang_up` and `fleet_deck.stop_all`. In attach mode stop --all runs `fabric-ctl all harness-stop`, and start --auto runs harness-start first.

Design (j167, approved by fabric-coordinator, REPLY 01a17ba4): each account runs a headless FleetDeck server (`--session harness`) as a user unit whose pane runs `enter --wait`. enter-ssh's word `attach` execs `terminal attach <pane>`, and moveto `--attach` reaches it. The deck's harness pane only attaches and is hung up off focus, which ends no agent. Rejected: saved machines and `--remote` (a whole-UI switch), tmux (a second multiplexer and prefix), dtach and abduco (not installed). The unit, enter-ssh, moveto and fabric-ctl are agent-fabric's (#435, #441); the deck side is the fork's (#49, #50, #54).

*References: events, j188-deck-tabs-setting*

*Observed 2026-11-03 (rust-ui-dev)*
