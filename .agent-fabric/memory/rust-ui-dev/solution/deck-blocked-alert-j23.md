---
role: "rust-ui-dev"
class: solution
topic: "deck-blocked-alert-j23"
description: Why a deck tab stays red after a permission prompt is answered, and where the blocked alert is (not) suppressed
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 12bf805dad17352b
---

## Why a deck tab stays red after a permission prompt is answered, and where the blocked alert is (not) suppressed

j23 (REQUEST 01a148e5, 2026-10-17): owner saw no sound/red when python-dev-03 hit a
PreToolUse-hook "ask" prompt, then red that stayed after answering.

- Red that stays: agent-fabric's session-state.py is registered on SessionStart,
  UserPromptSubmit, PreToolUse, PermissionRequest, Notification, Stop, SessionEnd
  (user-settings.py SESSION_EVENTS) — no PostToolUse, so an approved tool's whole
  run reads "blocked" until the next PreToolUse/Stop. agent-fabric's lane
  (fabric-coordinator); reported in REPLY 01a148e8.
- Alert path in herdr: a deck `report-agent` working→blocked sends a
  SemanticNotification with the Request sound (test
  src/server/headless/tests/transition_sounds.rs with_empty_tables...). The client
  (src/client/shell/notification_policy.rs tick_notifications) suppresses only the
  Finished sound on the active tab; the toast is skipped on the active tab. So a
  missing sound means the blocked report came late/never, a sound config, or a
  toast_delay validation drop — not active-tab suppression.
- The deck logs a stamped line per reported change (fabric_deck.py `_show`,
  status_line) in the operator's ~/.local/state/fabric-deck/deck.log — unreadable
  from this login; ask the operator for lines. I first told the coordinator it
  logged errors only (wrong; corrected in REPLY 01a148e9).

Timeline from the operator's deck.log (2026-10-17, UTC): python-dev-03 working 07:18:34,
permission 07:18:46, stale 07:48:41 (record ts stopped ~07:28:41: no heartbeat while
blocked — control plane's), permission 08:01:03 (the red the owner saw), working 08:06:34.
The stream did NOT go silent (25 accounts kept logging) — my silent-stream hypothesis was
refuted; the watchdog commit 6f92d7e5 on fix/j23-deck-stream-watchdog stays unpushed.
Owner's priority: the alert on the change to blocked (07:18:46Z: no sound, no red seen,
not on the tab, blocked sound configured). herdr at default log level records no state
changes or sounds, so it cannot be read back — reproduce instead.

Reproduced clean (debug 0.10.0, isolated server via HERDR_SOCKET_PATH under /run/user/<uid>,
client in `script -qfc` fed by `sleep N |` — never /dev/zero, it types NULs — and a fake
`paplay` first on PATH logging calls): no [ui.sound] config, deck's command sequence
working→blocked plays the request sound ~1.5 s later on a background and on the active tab.
So the live miss is live-server state (herdr answers success for a report it drops:
set_hook_authority_at). Deck now reads back `pane get` after each report and logs a
difference with agent + session owner: PR #39 (BlueTeam-OU/agent-fabric-fleetdeck).

#39 merged 2026-10-17 at 8808c1db (2 work, 2 fix; Codex failed twice with exit 101, third
run worked; two Codex findings: label failure after report-agent fixed, timeout-before-ack
judged not a defect — reading back after a timeout doubles the stall). Delivered in REPLY
01a14916 with the deploy + grep for the operator, and a proposal to keep blocked when stale
(tab-states contract, coordinator's lane). Live read-back pending from the operator.

j24 (2026-10-17): contract accepted (agent-fabric ad7be480, STALE row): stale after blocked keeps
blocked/stale with the red. Deck: `Deck.last_blocked[login]` learned from any record that lists
sessions (ctl's unknown row = live None says nothing), `display(track, live, last_blocked)` keeps
blocked only for State.RUNNING. PR #40; deploy only after the coordinator's agent-fabric PR merges.
#39 deployed by the operator at 8808c1db (controller pid 2903223); no read-back line right after.

#40 merged 2026-10-17 at 2aeb71ee (1 work, 4 fix) after 5 Claude rounds + 5 Codex rounds, each
Codex finding judged. Final design: `StreamRecords` (records dict) keeps `listed` (newest record
listing sessions; ctl's unknown [] row excluded) on every arrival; `not_running_at` + `record_at_cutoff`
stamped when the track is not RUNNING, ended only by a fresh record posted after the stamped one;
`blocked_since(listed, not_running_at)` feeds display(). Owner accepted the fail-safe trade-off
(a new harness's first blocked record read by the look that missed it can lose its red), recorded at
the cutoff. Deploy waits on the coordinator's agent-fabric PR with ad7be480. Follow-up P3: #41 (j25).
#41 merged 9b5a5c84 (j25): StreamRecords update/setdefault/|= go through __setitem__; update stores each entry in turn (Codex P3). Deploy with #40, after the coordinator's agent-fabric PR (ad7be480) merges.
Deployed 2026-10-17 ~11:59Z: agent-fabric #290 merged the STALE row; operator's deck at 9b5a5c84 (#40+#41), restarted. Coordinator relays any 'herdr holds' line.

*Anchors: `fleet-deck/fabric_deck.py::def _show`, `src/client/shell/notification_policy.rs::fn tick_notifications`, `src/server/headless/tests/transition_sounds.rs::fn with_empty_tables_the_server_sends_what_upstream_sends`*

*Observed 2026-10-17 (rust-ui-dev)*
