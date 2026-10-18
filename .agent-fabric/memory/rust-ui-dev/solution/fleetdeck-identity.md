---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-identity"
description: "The herdr fork is Agent Fabric FleetDeck (agent-fabric-fleetdeck) from 0.10.0: what was renamed, what kept HERDR_* on purpose, the foreign-pane rule, and the release guards against Herdr's tags"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 5614e36105d58352
---

## The herdr fork is Agent Fabric FleetDeck (agent-fabric-fleetdeck) from 0.10.0: what was renamed, what kept HERDR_* on purpose, the foreign-pane rule, and the release guards against Herdr's tags

The herdr fork became Agent Fabric FleetDeck on branch develop-qzapp/rust-ui-dev-01/feat/fleetdeck-identity (j64, 2026-10-10; owner spec via fabric-coordinator REQUEST 01a1271c). Verify on main before relying on it.

- Executable/package `agent-fabric-fleetdeck`, version 0.10.0 (inherited 0.9.3 + MINOR for the breaking rename, below 1.0). `src/identity.rs` holds BIN_NAME, PRODUCT_NAME, REPOSITORY_URL.
- Dirs: `app_dir_name()` is `agent-fabric-fleetdeck` / `agent-fabric-fleetdeck-dev` (config, state, sockets). Socket and log file names inside stay `herdr.sock` etc.
- Every pane/popup/plugin gets `AGENT_FABRIC_FLEETDECK=1` beside `HERDR_ENV=1`. At start, main drops every `HERDR_*` var when HERDR_ENV=1 without the marker (inside a Herdr or pre-0.10 fork pane). The fleet deck applies the same rule (`fleet-deck/fabric_deck.py` fleetdeck_env). Tests that fake a pane must set the marker.
- Kept on purpose: HERDR_* pane/plugin/hook env, herdr-plugin.toml, integration hook file names, TERM_PROGRAM=herdr, config keys. docs/, skill file, CHANGELOG are Herdr's text; `--skill` rewrites `herdr ` to the binary at print time.
- Updates read raw.githubusercontent.com/BlueTeam-OU/agent-fabric-fleetdeck/master/distribution/{latest,preview}.json. latest.json is `0.0.0` with no assets until the first release, and the first release tag names `Previous-Stable: none`. `scripts/release.py require_fleetdeck` refuses any source whose Cargo package is not agent-fabric-fleetdeck. Workflows are guarded to repo BlueTeam-OU/agent-fabric-fleetdeck, so they are dormant until the owner renames the repository.
- `fleet-deck/install` (j65) hands panes from a pre-rename `herdr` server only with `--from-herdr`, after `herdr --default-config` shows `socket_access` (in every fork build from 5a8635cd, absent upstream); the plan itself drops a herdr source otherwise, and it refuses when the flag cannot act. Live trial 2026-10-11: counter kept counting across the handoff. Moved agents' hooks keep herdr's socket until restarted.
- Docs: docs/fleetdeck/IDENTITY.md (migration, kept identifiers, setup left) and UPSTREAM.md (fork point, policy, import ledger).
- What FleetDeck's docs are (j73, PR #21 ce95a98f..9c8cbc5f, 2026-10-11): README.md, docs/fleetdeck/, fleet-deck/README.md, --help, --skill. docs/next|preview|versions (~45 files teaching macOS/Windows/Homebrew/herdr.dev) stay Herdr's verbatim — never rewrite them (sync conflicts, no FleetDeck website serves them); README.md says so and that their keys differ (ctrl+6).
- Release trap: `versions.mjs publish` copies docs/next/README*.md over the root READMEs; release.yml now `git checkout -- README.md README.zh-CN.md` right after and stages no README (pinned in scripts/release-workflows.test.ts).

**Why:** the owner wants an independent product that never loads, overwrites or talks to an upstream Herdr installation, with its own SemVer.
**How to apply:** new user-facing strings say `agent-fabric-fleetdeck`/FleetDeck. An upstream import that conflicts keeps FleetDeck's names and gets a row in UPSTREAM.md's ledger. See [[herdr-fork-baseline]], [[herdr-host-toolchain]].

*References: herdr-fork-baseline, herdr-host-toolchain*

*Observed 2026-10-10 (rust-ui-dev)*
