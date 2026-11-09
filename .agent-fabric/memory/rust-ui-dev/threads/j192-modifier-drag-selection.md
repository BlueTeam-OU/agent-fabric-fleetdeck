---
role: "rust-ui-dev"
class: threads
topic: "j192-modifier-drag-selection"
description: "j192: a modifier+drag in a mouse-reporting deck pane (e.g. an attached harness) makes a deck selection; where the routing lives and the plan sent"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - c891ae4af369e711
---

## j192: a modifier+drag in a mouse-reporting deck pane (e.g. an attached harness) makes a deck selection; where the routing lives and the plan sent

j192 (fabric-coordinator REQUEST 01a196f7, from develop-qzapp/user, 2026-11-01). Under `tabs = "all"`, every harness pane runs `terminal attach` to a Claude Code that turns on mouse reporting. So in the outer deck, a plain left drag is sent to the program and the owner cannot select. Shift+drag is the outer terminal's own selection, and it spans the whole deck.

Routing (master 25d13950, src/client/shell/mouse.rs `handle_mouse`):
- Down(Left) in a pane: `if hit.mouse_reporting && contains(inner_rect)` sends the press to the program and sets `pane_mouse_gesture`. Otherwise it anchors `crate::selection::Selection` (the double-click word path applies only with no modifier).
- Drag and Up use `active_selection_pane` and the `self.selection` finish/copy path, whatever the modifiers. The Up path honours copy_on_select and clipboard_shortcuts.
- Ctrl+left-click in Terminal mode with mouse_capture already means PaneLinkActivate (an earlier block), so the default modifier is alt.
- The right-click passthrough modifier parser is in src/config/model.rs (`parse_right_click_passthrough_modifier`, refuses shift). The client config copies it at src/client/shell/config.rs:162 and :381. src/main.rs:293 holds the commented default config.

Plan, sent in REPLY 01a196f8: a new ui setting, default "alt", "off" disables it. Tests: (1) modifier+drag selects and copies with no pane mouse event; (2) a plain drag still reaches the program; (3) with the setting off, the press is forwarded. Not verified: whether the owner's outer terminal sends alt in SGR drags. Delivery: a REPLY naming the PR, then a release build in ~/fleetdeck-builds (as in j190) for the coordinator.

Built (2026-11-01): PR #60, head e5ca1d5f, 1 work commit. The key is `ui.mouse_select_modifier`, default alt. It refuses shift and ctrl (ctrl+click is link activation, decided earlier in handle_mouse). The guard is an exact modifier match at the Down(Left) pane branch in mouse.rs.
- The mouse-transparency conformance harness (tests/input_conformance.rs `deliver`) ignores endpoint actions, so it scored the deck-kept alt gestures as failures (192 > 96). It now counts a gesture as owned when it left a selection in a reporting pane; the ratchet stays at 96.
- Live-verified through a real client: alt+drag copied the program's text, and the program got no bytes. See [[shell-client-live-mouse-check]].

- Review round 1 F1: alt+click with no motion was swallowed. Fix e18e4b6d: the press is held in `held_select_press` and sent to the program with the release when the selection is still a just-click. The harness owns a gesture only for a non-just-click selection.
- #60 MERGED 2026-11-01 (1 work, 1 fix; master 2813fdb2). F3 deferred: CHANGELOG is curated at release, and no fleet language-culture holder covers ja/zh-cn (holders ge/ru/en only).
- Release build ~/fleetdeck-builds/agent-fabric-fleetdeck-2813fdb2 (sha256 3e9b1073...). REPLY 01a1973b to develop-qzapp/user asks for the install and the owner's check. Coordinator REPLY 01a1973c took distribution (their j539); j192 done 2026-11-01. A defect returns as a new REQUEST. If the owner's terminal does not send alt, the answer is the setting (super/meta/hyper), not code.
- GitHub CI passed server_survives_hangup_and_logs_why_it_stops, which fails 3/3 locally (host-only).

Related: [[attach-pane-scroll-bar]], [[herdr-fork-prefix-ctrl6]], [[j188-deck-tabs-setting]]

*References: attach-pane-scroll-bar, herdr-fork-prefix-ctrl6, j188-deck-tabs-setting, shell-client-live-mouse-check*

*Observed 2026-11-01 (rust-ui-dev)*
