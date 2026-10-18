---
role: "rust-ui-dev"
class: workflow
topic: "upstream-remote-gh-default"
description: "With an `upstream` remote in the FleetDeck clone, gh targets herdrdev/herdr by default — pin gh to the fork before any gh write"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 06ce8da03e5b1672
---

## With an `upstream` remote in the FleetDeck clone, gh targets herdrdev/herdr by default — pin gh to the fork before any gh write

The fork's remit has `upstream` = https://github.com/herdrdev/herdr (push url `no-push`) for
syncs. Once that remote exists, plain `gh pr create` resolves the base repository to
herdrdev/herdr: on 2026-10-12 (j8, sync #27) it tried to open the sync PR upstream and failed only
because the branch was not there ("Head sha can't be blank ... No commits between").
Upstream closes unsolicited PRs and the remit forbids any PR or issue there.
**Why:** gh prefers a remote named `upstream` as the default repository.
**How to apply:** after adding `upstream`, run `gh repo set-default BlueTeam-OU/agent-fabric-fleetdeck`
(check with `gh repo set-default --view`), and pass `-R BlueTeam-OU/agent-fabric-fleetdeck` on gh writes.
A sync merge: `git merge --no-ff --no-commit <upstream sha>` on a branch off origin/master,
subject "merge herdrdev/herdr master into the fork (N upstream commits, through <sha>)", PR title
with `chore:` (CI checks the title); fork-identity adaptations of upstream text go in a separate commit.
Upstream's "docs: publish preview documentation" commit adds a distribution/preview.json
`builds[<id>]` entry with herdrdev download URLs; it merges cleanly and the updater falls back to
it (sync #27's P1). Empty its assets; scripts/test_distribution_offers_fleetdeck_only.py fails CI
otherwise. Check `--remerge-diff` and clean merges, not only the conflicts.

*Observed 2026-10-13 (rust-ui-dev)*
