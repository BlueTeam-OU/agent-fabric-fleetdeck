---
role: "rust-ui-dev"
class: solution
topic: "herdr-pane-focus-reporting"
description: "What a herdr pane learns about its own focus (DECSET 1004): every change, plus an answer to each set from its viewers' real focus (FleetDeck #38); an older server reports changes only"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 85f7bd88d1469ee9
  - ce87ca6a0fdfbfb8
---

## What a herdr pane learns about its own focus (DECSET 1004): every change, plus an answer to each set from its viewers' real focus (FleetDeck #38); an older server reports changes only

### What a herdr pane learns about its own focus (DECSET 1004): changes, plus an answer to each set; and why a focused plugin tab did not move clients

- **Since BlueTeam-OU/agent-fabric-fleetdeck#38 (j20)** the server answers every set of 1004 —
  also a set while the mode is already on — with the focus the pane's viewers really give it:
  `\e[I` iff an active shell client whose outer terminal has focus (`outer_terminal_focus ==
  Some(true)`) shows the pane as its tab's focused pane, `\e[O` otherwise. The server's default
  target is never evidence: with no client attached the answer is out, though `pane list` says
  focused. Code: `src/pane/focus_reporting.rs` (tracker; C0 and DEL inside a sequence pass
  through, CAN/SUB cancel, as Ghostty's parse_table), `ProcessBytesResult.focus_reporting_set`,
  `HeadlessServer::answer_focus_reporting_set` (`src/server/headless/client_views.rs`). Focus
  *changes* are still forwarded as before (`sync_focus_events`, per-client shell transitions).
- **An older server reports changes only**: a pane focused before its program enables 1004 gets no
  focus-in, and one opened in a background tab no focus-out. So the views keep their fallback:
  focus unknown until a report or a key, and `FABRIC_VIEW_OPENED_FOCUSED=1` from the opening action.
- **Attached clients keep their own tab surface** (`src/server/headless/client_views.rs`); a public
  create moves them only via `public_create_requests_focus`, which the fork extends to
  plugin.pane.open (commit 3ed20ab8). Upstream herdrdev/herdr has the bug.
- **Testing live under a scratch XDG_CONFIG_HOME leaks into the panes** (gh finds no login,
  fabric-jobs reads an empty store); and a fresh config's first-run screen eats keys typed into a
  pty client, so drive the pane with `pane send-text`.

Verified live 2026-10-16 on develop-qzapp (throwaway debug server, pty client); see [[focus-on-1004-j20]].

*References: focus-on-1004-j20*

*Anchors: `src/server/headless/client_views.rs::answer_focus_reporting_set`, `src/pane/focus_reporting.rs::FocusReportingSetTracker`, `src/pane/focus_reporting.rs::passes_through_sequence`*

*Observed 2026-10-16 (rust-ui-dev)*
