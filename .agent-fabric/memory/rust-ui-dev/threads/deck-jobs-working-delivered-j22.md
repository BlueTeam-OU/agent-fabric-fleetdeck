---
role: "rust-ui-dev"
class: threads
topic: "deck-jobs-working-delivered-j22"
description: "j22 (REQUEST 01a14483, coordinator): deck job counts split working vs delivered; on PR #37; state and how to read back"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - e3db4bece13fdb67
---

## j22 (REQUEST 01a14483, coordinator): deck job counts split working vs delivered; on PR #37; state and how to read back

j22 = REQUEST 01a14483-1815 from the coordinator (2026-10-16): the owner read devex-tooling's job count (67 delivered,
1 active, 3 queued) as open work. ADR-037 OPEN (agent-fabric tools/fabric/jobsparts/base.py:59) includes delivered on purpose.
Answered REPLY 01a14484-2e82 (taken, on #37). Commit 3f895b71 on the j21 branch, PR #37 (see [[tab-rows-config-j21]]):
view_render.py WORKING/working_jobs/delivered_jobs; board "closed/working" + "delivered" column (drop 8, first to go);
agent view "Working jobs (N)" + "Delivered, waiting on a merge (N)"; compare metrics working + delivered (7 metrics,
hints derived from len(METRICS)). Fixture test class WorkingAndDelivered (mutation: delivered in WORKING fails 3).
Acceptance read-back on devex-tooling's real list needs the operator login (`user`): this login sees ? for jobs
([[fleet-deck-snapshot]]). Review of the j22 commit + codex round 6 running. Tell the coordinator the PR/head on merge.
- j22 review (claude 5547389401): P3 README 1-6/open, P3 delivered heading hidden at 0; risk unknown states. Codex r6
  none. Fixed 11b8e05a: NOT_WORKING = delivered/done/dropped (unknown state = work), delivered heading always with
  count or none. #37 = 3 work, 6 fix; re-review + codex r7 running on 11b8e05a.
- Codex r7 P2 (delivered count cut at 30 cols) fixed a25f861e ("Delivered jobs (N)" + dim explanation line). On
  a25f861e: claude 5547493374 none, codex r8 none. #37 = 3 work, 7 fix; CI pending; arm needs the owner's word.
- Merged in #37 (ab5e4d24). REPLY 01a144f5-4332 asks the coordinator to read back devex-tooling's tab as operator.
  j22 is `delivered` until that read-back; then done.

*References: fleet-deck-snapshot, tab-rows-config-j21*

*Observed 2026-10-16 (rust-ui-dev)*
