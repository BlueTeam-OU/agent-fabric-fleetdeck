---
role: "rust-ui-dev"
class: rationale
topic: "fleetdeck-linux-only-keeps-platform-code"
description: "Why FleetDeck's Debian/Fedora-only rule (2026-10-11) refuses non-Linux at entry points but keeps upstream's macOS/Windows code"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-12"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 653fae7d3d5c1367
---

## Why FleetDeck's Debian/Fedora-only rule (2026-10-11) refuses non-Linux at entry points but keeps upstream's macOS/Windows code

The owner's rule of 2026-10-11: FleetDeck is Debian and Fedora only. CI and release
publish linux-x86_64 and linux-aarch64 only (#19); `src/update.rs` `RELEASED_TARGETS`
names them and is production code since the j71 follow-up branch
`develop-qzapp/rust-ui-dev-01/fix/linux-only-remote-install`.

Decided (rust-ui-dev-01, j71): upstream's macOS/Windows code stays — src/platform/{macos,windows}
(~8.7k lines), vendor/portable-pty/src/win, distribution/install.ps1 (embedded by update.rs
WINDOWS_INSTALLER and used by remote Windows install), the Windows scripts and their tests.
It is compile-gated, never in a Linux binary, and deleting it (417 cfg sites, 75 files) would
turn every upstream sync into a conflict, against the remit's "the fork's own changes stay small".

What a person meets refuses up front instead: `install.sh` on Darwin, and remote attach to a
macOS/Windows host without an installed FleetDeck or HERDR_REMOTE_BINARY
(`refuse_unreleased_platform` in src/remote/attach.rs) — before it asked to approve an install
and failed on the missing asset after the yes.

**Why:** zero cost in Linux binaries, large cost in sync; the defect was the late failure.
**How to apply:** a new entry point that downloads a release asset checks RELEASED_TARGETS
first. See [[herdr-fork-ci-platforms]], [[fleetdeck-identity]].

*References: fleetdeck-identity, herdr-fork-ci-platforms*

*Observed 2026-10-11 (rust-ui-dev)*
