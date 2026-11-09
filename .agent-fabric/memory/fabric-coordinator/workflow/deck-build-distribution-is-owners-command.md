---
role: "fabric-coordinator"
class: workflow
topic: "deck-build-distribution-is-owners-command"
description: "how a merged herdr fleet-deck change reaches the operator deck: ff the shared checkout and run its fleet-deck/install, the owner's command from a terminal"
tier: 1
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: user
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 116bc21375d69b87
---

## how a merged herdr fleet-deck change reaches the operator deck: ff the shared checkout and run its fleet-deck/install, the owner's command from a terminal

The operator deck's `~/.local/bin/fleet-deck` links into the shared checkout `~/projects/herdr` (master), not a job worktree, so a merged deck change reaches it by fast-forwarding that checkout and running `~/projects/herdr/fleet-deck/install` there (builds `agent-fabric-fleetdeck`, installs by rename, live-handoff of the running server; never stops a pane).

From a job session the ff is refused by the job-copy guard (agent-fabric ADR-037 rule 3: a `git merge` outside the job's working copy), and the installer must run from an ordinary terminal, not a pane (`server.socket_access = "outside_panes"`). So the coordinator checks it (shared checkout clean, `merge-base --is-ancestor`, `install --dry-run` from the worktree, which also passes the Zig version check) and hands the owner one line: `! git -C ~/projects/herdr pull --ff-only && ~/projects/herdr/fleet-deck/install`. Done this way for j539 (herdr #60, 2026-11-01). See [[deck-live-readback-recipe]].

*References: deck-live-readback-recipe*

*Anchors: `herdr:fleet-deck/install`, `herdr:fleet-deck/README.md`*

*Observed 2026-11-01 (fabric-coordinator)*
