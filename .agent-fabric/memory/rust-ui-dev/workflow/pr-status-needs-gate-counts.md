---
role: "rust-ui-dev"
class: workflow
topic: "pr-status-needs-gate-counts"
description: "any PR named in a reply (mine or another agent's, any repo) needs \"#N (W work, F fix)\" from fabric-pr gate, or the Stop hook blocks the reply"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - d75855158de2c3ef
---

## any PR named in a reply (mine or another agent's, any repo) needs "#N (W work, F fix)" from fabric-pr gate, or the Stop hook blocks the reply

The Stop hook `runtime/claude-code/hooks/pr-counts.py` refuses a reply that names a PR's status without its counts, including another agent's PR (gzapi-org/InterWeave#250, 2026-10-10) and repeat status lines in quiet watch-expiry replies.

**Why:** the owner decides arming from what the reply says.

**How to apply:** run `fabric-pr gate` (own PRs) or `fabric-pr gate --all` (others') from that project's working copy (cd there; `-R` is not accepted) and write "#N (W work, F fix)" for every PR mentioned. Related: relayed arming on the owner's word ("fabric-pr arm N --basis ...") was refused by the auto-mode classifier as merge-without-review on 2026-10-10 — the owner arms it, or says so in session.

*Observed 2026-10-10 (rust-ui-dev)*
