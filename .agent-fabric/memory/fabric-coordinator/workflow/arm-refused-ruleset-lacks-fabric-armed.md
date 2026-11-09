---
role: "fabric-coordinator"
class: workflow
topic: "arm-refused-ruleset-lacks-fabric-armed"
description: "fabric-pr arm refuses on a repo whose ruleset predates ADR-019 A 2026-11-01 (no fabric/armed required check); applying it is the owner's decision (j551)"
tier: 1
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: user
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 69a9952da2b0f95d
---

## fabric-pr arm refuses on a repo whose ruleset predates ADR-019 A 2026-11-01 (no fabric/armed required check); applying it is the owner's decision (j551)

Since ADR-019 A 2026-11-01 (#454, `armed_status`), every mode-`auto` arming policy requires `fabric/armed` as a status check, and `fabric-pr arm` (dry-run included) refuses a repo whose GitHub ruleset still lists only its old checks: "GitHub settings differ from its arming policy — rule required_status_checks". On 2026-11-03 BlueTeam-OU/agent-fabric-fleetdeck (ruleset 24884010, untouched since 2026-10-11) refused #61 that way; BlueTeam-OU/agent-fabric did the same on 2026-11-01.

`fabric-repo-policy apply <repo>` fixes it, but the auto-mode classifier refused it as Modify Shared Resources, so it waits on the owner's decision (j551): they run it, allow it in policies/auto-mode.json, or set `armed_status` null for the repo. Until then, a drain half or any other PR on such a repo gets reviewed and is then blocked on j551. Check with `fabric-repo-policy plan <owner/repo>` before promising an arm.

Resolved for both repos: j551 closed done, and on 2026-11-04 `fabric-repo-policy plan BlueTeam-OU/agent-fabric-fleetdeck` read "GitHub matches the arming policy"; #61 then armed at the count rule (1 work, minimum 1) and merged on head 992581a0. The fleetdeck ruleset is not strict (no up-to-date requirement), so a PR behind master needs no merge-from-master push before arming — pushing one only moves the head off the reviewed one.

*Anchors: `agent-fabric:tools/fabric/github/arm.py::armed_status`*

*Observed 2026-11-04 (fabric-coordinator)*
