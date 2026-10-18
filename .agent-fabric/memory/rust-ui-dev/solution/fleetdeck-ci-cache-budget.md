---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-ci-cache-budget"
description: "FleetDeck CI's 10 GB Actions cache — which keys churn, why debian saves were slow, how to measure a cache's worth"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 0737c3e955fb1932
---

## FleetDeck CI's 10 GB Actions cache — which keys churn, why debian saves were slow, how to measure a cache's worth

BlueTeam-OU/agent-fabric-fleetdeck shares one 10 GB Actions cache store (LRU eviction).
On 2026-10-18 it was full (10.10 GB): `ci-incremental-v1-<leg>` keyed on github.sha
(~1.5 GB/leg) and `zig-build-v1-<leg>` keyed on run_id (~0.5 GB/leg) were saved on every
master push and evicted the reusable ones (the ubuntu Swatinem `v0-rust-*` entry is only
~0.35 GB). PR #42 (j106) keys zig-build on `hashFiles('vendor/libghostty-vt/**',
'crates/ghostty-vt/build.rs')` with save-on-miss, and drops the incremental cache.

- debian:12 has no `zstd`: actions/cache falls back to single-threaded `tar -z`
  (85 s to compress 1.5 GB, upload 2 s). Fedora 42 and ubuntu-latest have it.
- Any cache key ending in sha/run_id with a prefix restore-key is a new entry per push:
  check the store with `gh api repos/<r>/actions/cache/usage` and `gh cache list`.
- To judge a cache, pull per-step timings from the jobs API and grep job logs for
  "Cache restored from key" / "Cache not found" — every run hitting gives no miss
  measurement; a PR without the cache is the measurement.
- A change to `.github/workflows/ci.yml` is a security-boundary change for `fabric-pr arm`:
  it needs a review-class review of the head before arming.

*Anchors: `.github/workflows/ci.yml::zig-build-v2`, `.github/workflows/ci.yml::zstd`*

*Observed 2026-10-18 (rust-ui-dev)*
