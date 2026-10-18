---
role: "rust-ui-dev"
class: solution
topic: "plugin-pane-label-is-title"
description: "FleetDeck labels a plugin pane with its manifest title and lists an overlay in its tab — a title equal to a deck role label is read as the deck's pane"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 20fdd685806cfe24
---

## FleetDeck labels a plugin pane with its manifest title and lists an overlay in its tab — a title equal to a deck role label is read as the deck's pane

FleetDeck (the herdr fork) gives a plugin pane opened from `herdr-plugin.toml` the pane
`label` = its `[[panes]] title`, and `pane list` shows an overlay with the `tab_id` of the
tab it covers (seen live on 2026-10-15, with a debug build of master 5fc17333). So a
plugin pane titled like a deck role (`harness`/`shell`/`status`/`agent`, deck_tabs.PANE_ROLES)
is taken for that role by `read_tab` and by the toggle. That is why the overlay's title
became "this agent" in PR #33 (j15), and test_fabric_view pins the manifest title
against PANE_ROLES.

Related facts from the same check:
- `pane zoom <id> --on|--off` focuses the pane it names (app/actions.rs apply_pane_zoom).
- The plugin manifest is re-read from disk on every key-bound action invoke and plugin
  pane open (`refresh_installed_plugins`): a manifest change needs no relink.
- `plugin action invoke` returns before the action's command finishes. Two invokes in a
  row run at the same time and both see the same focus, so a live test must sleep
  between presses.
- A process in a pane cannot call the socket (`socket_access = outside_panes`): only a
  plugin action or the deck can zoom, focus or `pane run`.

**Why:** when the overlay was titled "agent", every repeated press opened another overlay.
**How to apply:** give any new plugin pane title a name outside PANE_ROLES. Test the
toggle and other plugin actions one press at a time.

**Focus facts (j15, #33, checked live 2026-10-15):**
- herdr sends a pane focus reports (DECSET 1004) only on a change, and drops any change made before
  the pane turns reporting on. A view started in an already focused pane never hears a focus-in.
- `pane send-text <pane> "\x1b[O"` writes the bytes raw to the pty, and a 1004 view reads them as
  a real focus report. That is how the deck tells a view its focus once its title shows it can hear.
- `pane list` `focused` is true only for the active tab's focused pane, at most one pane in all.
- A pane's shell starts as `/bin/bash` with no arguments. A "bare shell" check must allowlist
  options: `-c`, fish `--command=` and scripts read what is typed.

*References: panes*

*Anchors: `fleet-deck/herdr-plugin.toml::this agent`, `fleet-deck/fabric_view.py::OVERLAY_TITLE`, `src/app/actions.rs::apply_pane_zoom`*

*Observed 2026-10-15 (rust-ui-dev)*
