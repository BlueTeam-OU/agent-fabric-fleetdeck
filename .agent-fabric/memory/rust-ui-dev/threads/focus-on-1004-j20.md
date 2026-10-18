---
role: "rust-ui-dev"
class: threads
topic: "focus-on-1004-j20"
description: "j20 — the server answers a pane's DECSET 1004 with its viewers' real focus; merged as #38; limit accepted; deployed and read back 2026-10-16"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 9aca921f82e195d1
---

## j20 — the server answers a pane's DECSET 1004 with its viewers' real focus; merged as #38; limit accepted; deployed and read back 2026-10-16

j20 (follow-up to FleetDeck #36, see [[deck-pane-tabs-j18]]), branch develop-qzapp/rust-ui-dev-02/feat/j20-herdr-a-pane-that-turns-on.
- Precedent: Ghostty's app layer (vendor/libghostty-vt/src/termio/stream_handler.zig `.focus_event`) answers
  every 1004 set with the current focus, in or out; herdr's vt core has no such layer, so herdr reported changes only.
- Design at 2b8483a1: src/pane/focus_reporting.rs `FocusReportingSetTracker` (byte parser, catches a set while already
  on) + mode edge in process_pty_bytes -> `ProcessBytesResult.focus_reporting_set` -> AppEvent::TerminalFocusReportingSet
  -> HeadlessServer `answer_focus_reporting_set` (client_views.rs): Gained iff an active shell client with
  outer_terminal_focus Some(true) has the pane as shell_focus_target; Lost otherwise. TerminalAttach clients are outside
  herdr's focus model (no focus handling there) and stay out.
- 2026-10-16 owner decisions: limit ACCEPTED (no vt-core hook job); deploy REQUEST 01a14622-aa2a-7f27-86c8-c1dd5a7b54d7
  sent TO develop-qzapp/user (fabric-coordinator) with read-back a-f; the control for "answer on set" is
  `sleep 5; printf '\e[?1004h'; cat -v` + switching tab (new server ^[[O^[[I, old ^[[I only). DEPLOYED 2026-10-16 (REPLY 01a14641): a-e pass on the
  operator's deck (617a0951, 120/120 panes kept, ^[[I on set, control ^[[O^[[I, agent pane live without a key).
- MERGED 2026-10-16: BlueTeam-OU/agent-fabric-fleetdeck#38 at 6b47d9e6 (3 work, 4 fix). Not live until the operator
  runs fleet-deck/install + handoff (Rust change), see [[deck-delivery-read-back]]. Open owner choice: accept the
  tracker's documented limit (C1 CSI breaking into strings/[redacted]/intermediates unseen) or a vendored libghostty-vt
  hook reporting each applied DECSET; five review rounds each found another table divergence of the hand parser.
- 2026-10-16: tests (b4fac6a5) and deck docs (76286065) added; PR BlueTeam-OU/agent-fabric-fleetdeck#38 opened,
  blind review dispatched on 76286065. Live-checked on a throwaway debug server (no client -> \e[O although pane list
  says focused; pty client with terminal focus -> \e[I; after focus-out -> \e[O). Typed keys in a fresh-config pty
  client are eaten by its first-run screen: send the trigger with `pane send-text` instead.
- Full local suite: run the unit binary one top-level module per process (SIGPIPE trap); a filter like `tests::`
  matches every module and hits the trap again.
- Tests that make git commits need GIT_CONFIG_GLOBAL=/dev/null (gpg signing), see [[fork-local-test-traps]];
  the cargo bin target is `agent-fabric-fleetdeck` (`cargo test --bins -- <filter>`).

*References: O^[[I, old ^[[I only). DEPLOYED 2026-10-16 (REPLY 01a14641): a-e pass on the
  operator's deck (617a0951, 120/120 panes kept, ^[[I on set, control ^[[O^[[I, agent pane live without a key).
- MERGED 2026-10-16: BlueTeam-OU/agent-fabric-fleetdeck#38 at 6b47d9e6 (3 work, 4 fix). Not live until the operator
  runs fleet-deck/install + handoff (Rust change), see [[deck-delivery-read-back, deck-pane-tabs-j18, fork-local-test-traps*

*Observed 2026-10-16 (rust-ui-dev)*
