---
role: "rust-ui-dev"
class: workflow
topic: "fork-build-zig"
description: "How to build the FleetDeck fork on develop-qzapp — Zig 0.16 is not on the host; rust-ui-dev-02 keeps one in its home"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - c8f6b29010bf60ba
---

## How to build the FleetDeck fork on develop-qzapp — Zig 0.16 is not on the host; rust-ui-dev-02 keeps one in its home

develop-qzapp has no Zig and no rustup (system cargo 1.98.1; rust-toolchain.toml pins 1.96.1,
ignored without rustup). The fork's crates/ghostty-vt needs Zig 0.16.0
(vendor/libghostty-vt/build.zig.zon), even for `cargo check`. On 2026-10-11, with the owner's
approval, rust-ui-dev-02 installed the official tarball (sha256 checked against
ziglang.org/download/index.json) at ~/.local/share/zig-0.16.0; build with
`ZIG=$HOME/.local/share/zig-0.16.0/zig cargo ...`. `just` is not installed either: run the
justfile's commands directly.
**Why:** each login needs its own copy until devex-tooling provides one host-wide.

*Observed 2026-10-11 (rust-ui-dev)*
