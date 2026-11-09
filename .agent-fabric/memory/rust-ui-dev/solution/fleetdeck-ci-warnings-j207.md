---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-ci-warnings-j207"
description: "FleetDeck CI warnings (j207, 2026-11-04): build.rs contributor-policy cargo:warning removed in #62; keep it out on upstream sync; rerun by the head's run id"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - c9a58fac10cbbf30
---

## FleetDeck CI warnings (j207, 2026-11-04): build.rs contributor-policy cargo:warning removed in #62; keep it out on upstream sync; rerun by the head's run id

fabric-ci-warnings on BlueTeam-OU/agent-fabric-fleetdeck (2026-11-04, 10 runs) found two kinds of line:
- upstream's `build.rs` `cargo:warning=external contributor policy: ...`, one per cargo step of every check job. #62 (d3d1a6d0) deletes it. An upstream sync that touches build.rs can bring it back, and no test pins its absence: drop it again in the sync merge.
- the Ubuntu 26 notice on ubuntu-latest: no action, per the owner (REQUEST 01a1a3f0).
- Not in CI: the host's rustc 1.99 flags `fetch_update` as deprecated at src/client/endpoint/writer.rs:137. The 1.96.1 pin doesn't; it goes with the toolchain bump.

Lessons:
- The fork's conventional-commits check allows only chore, ci, docs, feat, fix, perf, refactor, release, test. A `build:` subject is red; use `chore(build):`.
- After a force-push, `gh run rerun <id> --failed` must name the new head's run (`gh run list --branch ... --json headSha`). Re-running the old head's run shares the concurrency group and cancelled a job on the new head.
- Arm refused #62 because the fleetdeck ruleset lacks `fabric/armed` (fleet default since agent-fabric#454). fabric-coordinator applies it; the owner's hand is needed (REPLY 01a1a402).

See [[herdr-host-toolchain]], [[fleetdeck-identity]].

After merge (2026-11-04, master 2a36a674): the policy warning is gone. The Nix flake check shows 4 log lines: 3 dependency file names containing "deprecated" (gettext, harfbuzz), where the scan matched the word only, and nix's "omitted incompatible systems". They are not defects; the first scan missed them because no Nix run was among its 10.

*References: fleetdeck-identity, herdr-host-toolchain*

*Anchors: `build.rs::rerun-if-env-changed=HERDR_BUILD_COMMIT`, `src/client/endpoint/writer.rs::fetch_update`*

*Observed 2026-11-04 (rust-ui-dev)*
