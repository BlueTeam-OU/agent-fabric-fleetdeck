---
role: "rust-ui-dev"
class: workflow
topic: "review-tools-bound-to-clone"
description: "fabric-review MCP tools only serve the session's own clone: review another repository's PR from a session launched in that repository"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-31"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 8cc376c392256d3d
---

## fabric-review MCP tools only serve the session's own clone: review another repository's PR from a session launched in that repository

On 2026-10-26 a review of herdr fork PR #49 was dispatched from an interweave session. Every review_* tool refused the herdr clone and its pinned head worktree ("not the session's clone"). The report could not list the range, and `fabric-pr post-review` refused it: its coverage named paths outside the range.

**Why:** the review MCP server is bound to the session's working copy at launch.

**How to apply:** before dispatching a review of another repository's PR, switch to that job so the session runs in that working copy (fabric-jobs switch, then fabric-fresh). Do not dispatch it from the current session.

*Observed 2026-10-27 (rust-ui-dev)*
