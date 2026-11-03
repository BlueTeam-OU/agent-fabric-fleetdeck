---
role: "fabric-coordinator"
class: workflow
topic: "project-index-regen-recipe"
description: "Regenerating a managed project's role INDEX.md when fabric main gains domain slices, without a drain"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-31"
origin:
  - agent: user
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - bd9bbe2be0c04a08
---

## Regenerating a managed project's role INDEX.md when fabric main gains domain slices, without a drain

A project's `.agent-fabric/memory/<role>/INDEX.md` lists the role's fabric domain slices too, so it goes stale when fabric main gains some (herdr rust-ui-dev missed 12 on 2026-10-30). Fix without a drain: `tools/fabric/assemble.py --claims <empty dir> --drain <dir with references.json {} and empty observations.jsonl> --project <id> --fabric <fabric main> --working-copy <wc> --stamp <today> --reads-state <scratch file>`, then keep only INDEX.md files whose entries changed and revert last-drain-report.json, crossref.json and date-only INDEX rewrites; `lint.py --no-siblings --working-copy <id>=<wc>` confirms. Done that way in BlueTeam-OU/agent-fabric-fleetdeck#53 (herdr's remote; its arming minimum is 1 work commit), merged 2026-10-31.

*Anchors: `tools/fabric/assemble.py::--working-copy`, `tools/fabric/assembler/index.py::crossref`*

*Observed 2026-10-31 (fabric-coordinator)*
