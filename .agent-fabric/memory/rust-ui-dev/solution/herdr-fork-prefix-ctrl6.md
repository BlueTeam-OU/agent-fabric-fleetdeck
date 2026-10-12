---
role: "rust-ui-dev"
class: solution
topic: "herdr-fork-prefix-ctrl6"
description: "Why the herdr fork's prefix is ctrl+6, what herdr still takes from a pane, and how fleet-deck runs the deck detached"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-12"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - f4598a421d08903f
---

## Why the herdr fork's prefix is ctrl+6, what herdr still takes from a pane, and how fleet-deck runs the deck detached

On 2026-10-10, BlueTeam-OU/agent-fabric-herdr#13 (j58) changed the fork's default prefix from ctrl+b to **ctrl+6**. The owner asked for this ("every key combination forwarded to the harness as is"; "herdr command should be mapped in a way that we don't conflict with any harness").

**Why ctrl+6.** Among control keys, it is the only one bound by none of these:
- Claude Code: ctrl+b backgrounds the task, ctrl+_ is undo.
- Codex: its keymap.rs uses ctrl+], ctrl+/ and ctrl+7.
- bash's readline: binds every ctrl letter except c, z and \, plus ctrl+] and ctrl+_.
- The tty: ctrl+\ is SIGQUIT.

**Matching.** A legacy host sends ctrl+6 as 0x1e, which parses as ctrl+^. `legacy_ctrl_six_matches` in src/config/keybinds.rs makes a ctrl+6 binding match it there.

**The test.** `src/client/shell/tests/harness_keys.rs` holds the harness lists and a byte-for-byte check through the `HerdrPath` harness, which is made `pub(super)` in input_conformance.rs.

**Test fallout.** Upstream tests that sent 0x02 now send 0x1e. Watch for:
- Indexed ctrl digits lose ctrl+6, so two tests pin `prefix = "ctrl+b"`.
- In copy search, ctrl+b is the text editor's backward-char, not the prefix. Leave those test presses as 'b'.

**herdr's own keys.** The owner decided on 2026-10-10 (DECISION 01a1269e, INFO 01a1269f): ctrl+c, ctrl+v and plain PageUp/PageDown always reach the pane. herdr's actions moved:
- copy: ctrl+alt+c (`is_retained_selection_copy_key`);
- paste: ctrl+alt+p (`is_pane_paste_key`). Not ctrl+alt+v, which is Codex's fixed paste_image;
- scrollback: alt+PageUp/PageDown (`pane_input.rs`).
Both ctrl+alt keys are consumed even with nothing to do, because a legacy host sends ctrl+alt+c as ESC 0x03.

The owner's desktop keeps ctrl+alt+l, ctrl+alt+Esc, alt+digits, alt+comma, ctrl(+shift)+PageUp/PageDown and ctrl+shift+c/v (INFO 01a126a3). That list is pinned in harness_keys DESKTOP.

Input conformance treats these keys as owned (`forks_herdr_key`); its baseline stays at 60. `herdr terminal attach` still hard-codes ctrl+b q and plain-PageUp scroll.

**fleet-deck.** It double-forks fabric-deck into a session with no tty, and logs to `$XDG_STATE_HOME/fabric-deck/deck.log`. fabric_deck.main holds a POSIX record lock on deck.lock for its life (one deck per login), and lock_holder probes it with F_GETLK without taking it. A shared-flock probe made 679 of 3000 deck starts refuse (review of #13). Never call lock_holder inside the deck: closing any descriptor of the file drops its record lock. A ctrl+6 prefix also reserves ctrl+^, its legacy twin (legacy_twin). `stop` never stops herdr's server.

**The deck reads state first.** In live_of, a record whose state is "unknown" counts as no record (agent-fabric #179, coordinator rule 01a126de). That covers an unreadable session file and ctl's rows older than two heartbeats. `_note_befores` takes rises and falls only from fresh records. A missing state reads as "", not "unknown". This landed in #13 (2c48c62c). #179 is armed only after #13 merges and the deck restarts.

**End-to-end check.**
- Build the debug binary; it reads `$XDG_CONFIG_HOME/herdr-dev/`.
- Put that config dir under /run/user/<uid>, because of the socket path limit.
- Set `HERDR_SESSION`, use stub moveto and fabric-ctl, and attach through a python pty.

See [[herdr-host-toolchain]], [[herdr-socket-access-design]].

*References: herdr-host-toolchain, herdr-socket-access-design*

*Observed 2026-10-10 (rust-ui-dev)*
