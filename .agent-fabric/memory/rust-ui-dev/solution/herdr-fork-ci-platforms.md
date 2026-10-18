---
role: "rust-ui-dev"
class: solution
topic: "herdr-fork-ci-platforms"
description: "The herdr fork's CI first ran macOS and Windows on PR #14 (2026-10-11): what broke, why Linux can't see it, and which local cross-checks do not work on develop-qzapp"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 6b981a8ba1d85700
---

## The herdr fork's CI first ran macOS and Windows on PR #14 (2026-10-11): what broke, why Linux can't see it, and which local cross-checks do not work on develop-qzapp

Before BlueTeam-OU/agent-fabric-herdr #14, the fork's PRs ran CodeQL only. #14's CI was the first macOS and Windows run, and it surfaced defects from the fork's own earlier PRs (#3 socket_access, #4 clipboard keys, #13 harness keys) that Linux never compiles:

- **Dead code under `-D warnings`.** A helper used only by `#[cfg(unix)]` tests is dead on Windows; a platform reader is dead in test builds, because `default_clipboard_text_reader` swaps in `|| None` under `cfg(test)`. Fix the class: give helpers the same cfg as their callers, and give the platform readers `#[cfg_attr(test, allow(dead_code))]` with a reason (macos.rs, windows.rs).
- **Hand-copied key lists in conformance tests.** `forks_herdr_key` now asks the client's own predicates (`is_retained_selection_copy_key`, `is_pane_paste_key_for_platform`, with the platform as a parameter). Windows records name letters `vkNN`, mapped by `letter_of_virtual_key`.
- **Windows installer tests match messages and command names.** `scripts/test_windows_installer_messages.py` checks the expected refusals against install.ps1 on every platform.
- **The fleet-deck suite is Linux-only** (SO_PEERCRED, /proc, Linux's flock layout): `[linux]` recipe, plus a `[macos]`/`[windows]` notice.

Cross-checks that do **not** work on develop-qzapp: `cargo clippy --target aarch64-apple-darwin` gave no result within 25 minutes; `x86_64-pc-windows-gnu` is refused by the ghostty-vt build script ("unsupported target"); msvc needs the Microsoft SDK licence (see [[herdr-host-toolchain]]). CI is the only macOS and Windows check, so push early and read `gh run view --job <id> --log-failed`.

**Why:** a Linux-green change to `src/platform/`, cfg-gated tests or installer scripts has been red on the other two platforms every time so far.
**How to apply:** when touching cfg-gated code or a test helper, check every caller's cfg; never keep a second copy of a product predicate in a test.

*References: herdr-host-toolchain*

*Observed 2026-10-11 (rust-ui-dev)*
