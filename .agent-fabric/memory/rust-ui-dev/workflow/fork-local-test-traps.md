---
role: "rust-ui-dev"
class: workflow
topic: "fork-local-test-traps"
description: "Running the FleetDeck fork's tests and PR tools on develop-qzapp — false failures and the renamed-repo 307"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-12"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - b029feb985be8562
---

## Running the FleetDeck fork's tests and PR tools on develop-qzapp — false failures and the renamed-repo 307

Seen 2026-10-11 while building #18 (BlueTeam-OU/agent-fabric-fleetdeck):
- Tests that create git tags/commits in temp repos (cli plugin smoke test, 16 scripts/test_release*
  tests) fail under this account's global git config; they pass with
  `GIT_CONFIG_GLOBAL=/dev/null GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t`.
- Parallel `cargo test` gives EmptyResponse failures in cli/live_handoff/server_headless under load;
  `--test-threads=1` passes.
- Host clippy 1.98 > pinned 1.96.1 fails untouched code: filter
  `--message-format=short -- -W clippy::all` output to the changed files instead.
- No bun: docs-contract and integration-asset tests only run in CI.
- A throwaway server needs a short socket path: XDG_CONFIG_HOME/XDG_RUNTIME_DIR under /run/user/<uid>/,
  not the scratchpad (sun_path limit).
- While the clone's origin still names the old repo (agent-fabric-herdr), `fabric-pr post-review`
  gets HTTP 307 from GitHub; `GH_REPO=BlueTeam-OU/agent-fabric-fleetdeck fabric-pr post-review ...` works.

*Observed 2026-10-11 (rust-ui-dev)*
