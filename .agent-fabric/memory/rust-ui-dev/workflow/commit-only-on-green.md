---
role: "rust-ui-dev"
class: workflow
topic: "commit-only-on-green"
description: "Never put a commit or push in the same command line after a test run whose status is not captured — a `;` or a pipe lets a red suite commit and push"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - b1e3e5563d9b6a19
---

## Never put a commit or push in the same command line after a test run whose status is not captured — a `;` or a pipe lets a red suite commit and push

2026-10-16, FleetDeck #36 (j18): `python3 -m unittest … | tail -1; cd .. && git commit … && git push`
committed and pushed 914e0163 with a failing test, because `;` ran the commit whatever the suite said
and the pipe hid its exit status. A PreToolUse hook catches `check | filter && commit`, not `;`.
**Why:** a pushed red head costs a fix commit, a re-review and the reviewer's trust in the gate.
**How to apply:** run the suite to a log, capture `rc=$?`, read it, and commit in a separate command
only on 0. Never chain commit or push behind a test in one line.
- 2026-10-16 #37: a review-fix commit pushed with two rustc warnings CI denies (-D warnings). Before every push run
  `cargo build --all-targets --message-format=short | grep -E "^(src|tests)/.*warning"` and clippy with
  `-A clippy::chunks_exact_to_as_chunks` (host clippy 1.98 stops on vendored ghostty-vt otherwise).

*Observed 2026-10-16 (rust-ui-dev)*
