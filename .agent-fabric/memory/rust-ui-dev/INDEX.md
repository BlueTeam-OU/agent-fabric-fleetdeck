---
role: "rust-ui-dev"
class: index
description: "What rust-ui-dev knows and where it lives."
tier: 1
distilled_at: "2026-10-12"
---

# rust-ui-dev — knowledge index

A session is given the charter and brief (in the launch prompt),
and the project's remit with a pointer to this index (from the
session-start hook) — nothing below. Open a slice when its cue
matches what you are doing; a `workflow` slice says how a kind of
work is done here, so read the matching ones before that work.
Paths are relative to this working copy; `../agent-fabric/` is the
control plane checked out beside it.

## charter

- [`../agent-fabric/identities/roles/rust-ui-dev/charter.md`](../agent-fabric/identities/roles/rust-ui-dev/charter.md) — The fleet's native-client developer in Rust: the user interface on Slint across desktop and mobile, its accessibility, the client's local store and its privacy posture, and the acceptance tests a person's use of it must pass.

## brief

- [`../agent-fabric/identities/roles/rust-ui-dev/brief.md`](../agent-fabric/identities/roles/rust-ui-dev/brief.md) — How rust-ui-dev works day to day, in any project: a change begins from the person's journey, is designed as well as built, rests on agreed contracts, and is verified in the rendered client on every platform before it is called done.

## domain

- [`../agent-fabric/memory/domains/rust-ui-dev/domain/atspi-e2e-lessons.md`](../agent-fabric/memory/domains/rust-ui-dev/domain/atspi-e2e-lessons.md) — Driving a Slint/AccessKit window over AT-SPI in tests -- what the adapter answers, focus under Xvfb, hearing announcements, SELinux on this host
- [`../agent-fabric/memory/domains/rust-ui-dev/domain/slint-rendered-window-lessons.md`](../agent-fabric/memory/domains/rust-ui-dev/domain/slint-rendered-window-lessons.md) — Slint 1.18 layout/font traps the testing backend does not show -- monospace by name, wrap min-width, a component's height from its only child layout; look at the winit window under Xvfb

## solution

- [`.agent-fabric/memory/rust-ui-dev/solution/deck-unbound-role-new-workspace.md`](.agent-fabric/memory/rust-ui-dev/solution/deck-unbound-role-new-workspace.md) — Why FleetDeck put a new account's tab in workspace New, and why herdr cannot move it afterwards
- [`.agent-fabric/memory/rust-ui-dev/solution/fleetdeck-identity.md`](.agent-fabric/memory/rust-ui-dev/solution/fleetdeck-identity.md) — The herdr fork is Agent Fabric FleetDeck (agent-fabric-fleetdeck) from 0.10.0: what was renamed, what kept HERDR_* on purpose, the foreign-pane rule, and the release guards against Herdr's tags
- [`.agent-fabric/memory/rust-ui-dev/solution/fork-renamed-fleetdeck.md`](.agent-fabric/memory/rust-ui-dev/solution/fork-renamed-fleetdeck.md) — The herdr fork repository is BlueTeam-OU/agent-fabric-fleetdeck (renamed 2026-10-11); when to switch origin
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-agent-row-display.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-agent-row-display.md) — what a person actually reads in herdr's agent sidebar for a reported pane, and the report-metadata rules that bite
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-fork-baseline.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-fork-baseline.md) — Where the herdr fork began: upstream 3d9d2b18 (master 2026-10-06, version 0.9.3 = v0.9.3 + 46 unreleased commits); Herdr stable tags are side commits, never ancestors of master
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-fork-ci-platforms.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-fork-ci-platforms.md) — The herdr fork's CI first ran macOS and Windows on PR #14 (2026-10-11): what broke, why Linux can't see it, and which local cross-checks do not work on develop-qzapp
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-fork-prefix-ctrl6.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-fork-prefix-ctrl6.md) — Why the herdr fork's prefix is ctrl+6, what herdr still takes from a pane, and how fleet-deck runs the deck detached
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-host-toolchain.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-host-toolchain.md) — What building and checking the herdr fork needs on develop-qzapp beyond cargo, and which test failures are host artefacts
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-pane-focus-reporting.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-pane-focus-reporting.md) — What a herdr pane learns about its own focus (DECSET 1004): changes only, never the state at enable; and why a focused plugin tab did not move clients
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-restart-loses-moveto-agents.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-restart-loses-moveto-agents.md) — What a herdr server stop/restart keeps for moveto agent tabs, measured; consequences for fabric-deck and piece 2
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-restore-drops-plugin-panes.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-restore-drops-plugin-panes.md) — A herdr session restore keeps a plugin tab's label but runs a shell in place of the plugin's program; judge a tab by its process, not its label
- [`.agent-fabric/memory/rust-ui-dev/solution/herdr-sound-paths.md`](.agent-fabric/memory/rust-ui-dev/solution/herdr-sound-paths.md) — Where herdr decides and plays agent sounds (server vs client, shell vs attach), and how the fork's per-transition sounds hook in
- [`.agent-fabric/memory/rust-ui-dev/solution/moveto-sudo-own-pty.md`](.agent-fabric/memory/rust-ui-dev/solution/moveto-sudo-own-pty.md) — why herdr process-info on a moveto pane never shows claude — sudo use_pty puts the account on its own pty

## rationale

- [`.agent-fabric/memory/rust-ui-dev/rationale/deck-no-typing-into-sessions.md`](.agent-fabric/memory/rust-ui-dev/rationale/deck-no-typing-into-sessions.md) — Why the Fleet Deck flags an agent with no inbox watch on the board instead of typing a re-arm prompt into its session
- [`.agent-fabric/memory/rust-ui-dev/rationale/fleetdeck-linux-only-keeps-platform-code.md`](.agent-fabric/memory/rust-ui-dev/rationale/fleetdeck-linux-only-keeps-platform-code.md) — Why FleetDeck's Debian/Fedora-only rule (2026-10-11) refuses non-Linux at entry points but keeps upstream's macOS/Windows code
- [`.agent-fabric/memory/rust-ui-dev/rationale/rationale-carried-2026-10-10.md`](.agent-fabric/memory/rust-ui-dev/rationale/rationale-carried-2026-10-10.md) — Why herdr's socket switch filters callers instead of unbinding, how a peer is placed inside a pane, and what it means for fabric-deck

## workflow

- [`.agent-fabric/memory/rust-ui-dev/workflow/fork-build-zig.md`](.agent-fabric/memory/rust-ui-dev/workflow/fork-build-zig.md) — How to build the FleetDeck fork on develop-qzapp — Zig 0.16 is not on the host; rust-ui-dev-02 keeps one in its home
- [`.agent-fabric/memory/rust-ui-dev/workflow/fork-ci-traps.md`](.agent-fabric/memory/rust-ui-dev/workflow/fork-ci-traps.md) — herdr fork CI traps — conventional-commit check on PR title and every subject; master has no required checks
- [`.agent-fabric/memory/rust-ui-dev/workflow/fork-local-test-traps.md`](.agent-fabric/memory/rust-ui-dev/workflow/fork-local-test-traps.md) — Running the FleetDeck fork's tests and PR tools on develop-qzapp — false failures and the renamed-repo 307
- [`.agent-fabric/memory/rust-ui-dev/workflow/mutation-restore-mtime.md`](.agent-fabric/memory/rust-ui-dev/workflow/mutation-restore-mtime.md) — A mutation check restored with cp/mv from a backup leaves cargo running the mutant — touch the file after restoring
- [`.agent-fabric/memory/rust-ui-dev/workflow/pr-status-needs-gate-counts.md`](.agent-fabric/memory/rust-ui-dev/workflow/pr-status-needs-gate-counts.md) — any PR named in a reply (mine or another agent's, any repo) needs "#N (W work, F fix)" from fabric-pr gate, or the Stop hook blocks the reply
- [`.agent-fabric/memory/rust-ui-dev/workflow/workflow-carried-2026-10-10.md`](.agent-fabric/memory/rust-ui-dev/workflow/workflow-carried-2026-10-10.md) — Codex was removed from gzapi-org on 2026-10-09: never wait for a Codex review; still check for unresolved threads before calling the gate met

## threads

- [`.agent-fabric/memory/rust-ui-dev/threads.md`](.agent-fabric/memory/rust-ui-dev/threads.md) — FleetDeck attention s2 (needs-you views) — ownership split, the view rules agreed, and where the contract lives

## recall

- [`../agent-fabric/identities/roles/rust-ui-dev/recall.md`](../agent-fabric/identities/roles/rust-ui-dev/recall.md) — Where rust-ui-dev's knowledge lives — charter, remit, distilled slices, this agent's memory — and how to trace a claim to its sources.
