---
role: "rust-ui-dev"
class: workflow
topic: "shell-client-live-mouse-check"
description: "How to prove a FleetDeck shell-client mouse/selection change through a real client in a pty, and the DISPLAY=:0 trap that writes the operator's clipboard"
tier: 1
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 23ed57bdf31edcb0
---

## How to prove a FleetDeck shell-client mouse/selection change through a real client in a pty, and the DISPLAY=:0 trap that writes the operator's clipboard

Recipe (j192, PR #60, 2026-11-01). `pane send-text` drives a pane's program, not the outer shell client, so it cannot exercise client routing or selection. Instead:
- Unset every HERDR_* and AGENT_FABRIC_FLEETDECK (an agent session runs inside a deck pane; they leak and break tests such as `agent_start_stops_retrying_when_the_pane_shell_stays_busy`). Then set HERDR_LOG yourself if you want debug logs (the unset loop removes it).
- XDG_CONFIG_HOME=/run/user/<uid>/<short> (socket path limit), with `onboarding = false` in agent-fabric-fleetdeck-dev/config.toml; extra `[ui]` keys go there.
- python `pty.fork()` runs `<debug bin> --session <name>`, set TIOCSWINSZ, wait ~4 s; `pane list` (JSON) gives the pane id; `pane run <id> "python3 prog.py log"`, where prog.py turns on `?1000h ?1002h ?1006h`, prints unique text and logs its raw input.
- Write SGR bytes to the pty (`\e[<b;col;rowM`, release `m`; +8 alt, +32 motion). Read the program's log for what reached it.
- The copy goes through xclip/xsel when DISPLAY is set (OSC 52 only over SSH/VSCode/WSL). The xclip owner dies with the client, so read the clipboard **while the client is alive**.

**Trap:** an agent session has DISPLAY=:0, the operator's display. A live run without a private `Xvfb :87` (and DISPLAY=:87 in the run) writes test text into the operator's clipboard. It happened once in j192 and was reported.

Related: [[herdr-host-toolchain]], [[attach-pane-scroll-bar]], [[j192-modifier-drag-selection]]

*References: attach-pane-scroll-bar, herdr-host-toolchain, j192-modifier-drag-selection*

*Anchors: `src/selection.rs::should_prefer_osc52`, `src/logging.rs::HERDR_LOG`, `src/client/shell/mouse.rs::mouse_select_modifiers`*

*Observed 2026-11-01 (rust-ui-dev)*
