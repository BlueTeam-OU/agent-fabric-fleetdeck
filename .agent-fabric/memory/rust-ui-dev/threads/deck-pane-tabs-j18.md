---
role: "rust-ui-dev"
class: threads
topic: "deck-pane-tabs-j18"
description: "FleetDeck sub-tab row (j18) — the design, the owner's F1-F4 chord, what is committed and what is left"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 2346337c6b1ea728
---

## FleetDeck sub-tab row (j18) — the design, the owner's F1-F4 chord, what is committed and what is left

j18 (REQUEST 01a14132, 2026-10-15): a yellow second tab row for account tabs, one pane shown at a time.
Plan sent as REPLY 01a14146 (seq 230760). Design, in the Rust client only, no wire change:
- `ui.pane_tabs` (src/config/model.rs, default harness/shell/status/agent); a tab qualifies when
  its panes carry exactly those labels, each once (src/client/shell/pane_tabs.rs `pane_tab_row`).
- The mark is the server's zoom: tab.zoomed && focused_pane_id. A pick sends
  Method::PaneZoom{pane_id, On} (zoom focuses the pane; an already zoomed tab stays zoomed).
- Layout gets a `pane_tabs` Rect between tab row and panes (config.rs layout, param `pane_tabs`);
  the existing snapshot->surface_size compare in shell_runtime.rs sends the resize.
Done at 0283ff75 (branch develop-qzapp/rust-ui-dev-02/feat/j18-fleetdeck-sub-tabs-a-second-tab):
config, row render, click, 3 unit tests. Still to do: keys (ctrl+6 then 1-4), deck zooms the harness
at build/restore, toggle (prefix+a) keeps zoom on, a rendered-frame + click test, live check.
**Open, the owner's:** prefix+1..9 is switch_tab by default; my recommendation (b) is 1-4 always
sub-tabs and switch_tab moved to prefix+alt+1..9. Wait for the answer before building keys.
Paused 2026-10-15 for urgent j19 (activity-dot fallback, REQUEST 01a14152), see [[ssh-pane-endpoint-match]].
- **Key conflict answered** (REPLY 01a14159-760e from the operator, 2026-10-15): the owner chose neither
  a nor b; ctrl+6 then 1-9 stays "go to tab N", sub-tabs get another chord, not yet named. Build the
  rest of the plan as written; the sub-tab binding is a config entry with no default until named.
- **Chord named** (REPLY 01a14172, 2026-10-15): ctrl+6 then F1-F4 = harness/shell/status/agent, the default.
  Indexed bindings now take F1-F9 and a `f1..f9` range (src/config/keybinds.rs `index_key`, `IndexRange`).
- Committed 2026-10-15 on the branch (unpushed until the PR): bf9262bc `pane.zoom_in_tab` (new method, CLI
  `pane zoom --no-focus`, schema artifact regenerated) and 8b3d389a select_pane_tab, default prefix+f1..f9.
  An earlier session left these edits uncommitted when it stopped; commit each unit as soon as it is green.
- Also committed: c2ec3b73 (row cells name their key, "F1 harness", from keys.select_pane_tab; render+click test),
  aa097240 (deck zooms the harness --no-focus at restore; prefix+a goes back to the harness zoomed), 86953f61 docs
  (config-reference.json needs every new config key: scripts/config_reference_check.py fails CI otherwise).
- An unknown API method gets `invalid_request` from an older server, not `unknown_method` (that code is only for
  retired graphics methods, src/api/server.rs).
- Live check done 2026-10-16 (tmux on a throwaway debug server, capture-pane): row, F3, prefix+1, click, --no-focus,
  focus reports all as required. PR FleetDeck #36 opened on head 86953f61; reviews round 1 running.
- server_headless::server_survives_hangup_and_logs_why_it_stops fails on this host on origin/master 0e5a444e too.
- Round 1 on #36 (posted 2026-10-16: claude 5540782490, codex 5540715816, adjudication 5540846611). Fix plan by class:
  A focus: deck polls view_ready after an unfocused background start and tell_focus once; restarts an ended agent
    view; server: PaneZoomInTab in shell_locations_may_need_reconcile (two-client focus-out). B one pane only where the
    row exists: _show_harness/toggle only on exact four-role tabs; main.rs `pane_tabs = []` comment honest.
  C `--no-focus` -> `--in-tab`; test the CLI's method choice; click-dispatch test (done, mouse_selection.rs).
  D _show_harness: log the error itself, once per tab per restore cycle (no re-zoom on retry). E zoom_in_tab out of
    sight does not reset state.mode. F mobile layout keeps the row under the header.
- Round-1 fixes pushed 2026-10-16: de19d3ae (Rust: focus transitions, mode, --in-tab, mobile row) and 08e4a494
  (deck: _hear, _restart_ended_views, exact-four zoom, harness_shown). Round 2 running (claude re-review + codex).
  The re-review brief was 83 KB (diff inlined); the dispatch pointed at the brief and findings files instead of
  pasting them — say so on the posted round.
- Rounds 2-3 (2026-10-16): fixes caf91edf/914e0163/73052633 (914e0163 was pushed red: see [[commit-only-on-green]]),
  28fa1d70, 72334483, 353d0698 pushed; round 4 running on 353d0698. Recurring Codex class across rounds 2-3: the
  deck's focus for a starting view comes from pane.list = the server's default target, not a client's own focus;
  judged P3 each time; full fix = a new server method (per-client viewer focus). If round 4 finds only that class,
  bring the owner the choice (fix first with a new method, or arm with the documented limit).
- 2026-10-16 rounds 4-5: Codex's focus class judged P3 (round 4) then P2 (round 5): a synthetic focus-in from
  pane.list (default target) leaves a hidden screen fetching after the last client detaches. Resolved on #36 by
  removing _hear (49e15bb0): the deck never tells a starting screen an inferred focus; a pick during startup
  waits for a key (prefix+a waits for the view). Proposed follow-up (QUESTION 01a1420b, awaiting the owner): the
  server sends a pane its viewers' real focus when it turns DECSET 1004 on (no API change; also fixes the deck's
  focused-start path). Round 6 running on 49e15bb0. Do not arm before the owner answers 01a1420b.
- 2026-10-16 ~00:45Z: #36 head cf62663e MERGEABLE per gate (6 work, 15 fix; claude + codex on head; checks green).
  Codex round 10 found the reverse trade (a pick during startup waits for a key), judged P3/product decision.
  Held unarmed for the owner's answer to 01a1420b (follow-up server fix vs. in #36). On "follow-up": arm with
  `fabric-pr arm 36 --basis ...`, then open a job for the server-side focus-on-1004 fix.

**Closed 2026-10-16.** The owner chose to merge with the limit documented (REPLY 01a142fb). #36 was armed and merged on head cf62663e (6 work, 15 fix). The delivery REPLY went out as 01a142fd. The coordinator fast-forwards the owner's deck and reads it back.
The limit that landed: the deck never infers focus, so a screen started without prefix+a says "press a key to go live". Lifting it is follow-up job j20, a per-client viewer-focus fix on the server side. A pane that turns on DECSET 1004 should hear its viewers' real focus, with no API change. That fix gets its own PR.

*References: commit-only-on-green, ssh-pane-endpoint-match*

*Observed 2026-10-15 (rust-ui-dev)*
