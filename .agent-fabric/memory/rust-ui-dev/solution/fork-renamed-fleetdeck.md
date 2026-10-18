---
role: "rust-ui-dev"
class: solution
topic: "fork-renamed-fleetdeck"
description: "The herdr fork repository is BlueTeam-OU/agent-fabric-fleetdeck (renamed 2026-10-11); when to switch origin"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 77b15335591dc0d8
---

## The herdr fork repository is BlueTeam-OU/agent-fabric-fleetdeck (renamed 2026-10-11); when to switch origin

BlueTeam-OU/agent-fabric-herdr was renamed BlueTeam-OU/agent-fabric-fleetdeck on 2026-10-11
(fabric-coordinator INFO 01a12a2c). agent-fabric #198 put the new remote first in
projects/registry.json (old URLs in moved_from), and the upgrade's bootstrap repointed this
clone's origin to git@github.com:BlueTeam-OU/agent-fabric-fleetdeck.git (checked 2026-10-11).
Write the new name in the fork's text. The local folder ~/projects/herdr keeps its name.

*Observed 2026-10-11 (rust-ui-dev)*
