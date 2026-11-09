---
role: "rust-ui-dev"
class: solution
topic: "harness-server-stale-binary"
description: "A fleetdeck fix that is merged and installed is still missing on the deck: the account's harness server predates it (exe '(deleted)'); check the start time before you write code"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 612f91c53009167d
---

## A fleetdeck fix that is merged and installed is still missing on the deck: the account's harness server predates it (exe '(deleted)'); check the start time before you write code

j210 (2026-11-04): the owner reported no scroll bar on a deck pane attached to an account's
harness. #57 (merged 2026-11-01) already draws it. /usr/local/bin/agent-fabric-fleetdeck
(installed 2026-11-02) draws it live: two throwaway --session servers, with thumb rows following
PageUp, PageDown and the wheel, and none with HERDR_CONFIG_PATH -> `pane_scrollbars = false`.
The cause: the server is what draws the attach frame, and each account's harness server
(`--session harness server`, agent-fabric-harness.service) had run since 2026-10-31 22:29.
`/proc/<pid>/exe` shows `(deleted)`.

How to apply: for any "the fix is not on the deck" report, compare
`systemctl --user show agent-fabric-harness.service -p ActiveEnterTimestamp` with the fix's
merge and install times first. The remedy is a harness restart, which ends the account's
running agent session ([[herdr-restart-loses-moveto-agents]]): that is the fabric's and the
owner's to schedule, not a code change. Live recipe: [[attach-pane-scroll-bar]].

Outcome: the deck read-back passed on 2026-11-04: fabric-coordinator restarted one harness unit while idle, and the owner saw the bar working over ssh (REPLY 01a1a607). the test commit 3629f534 rode #62 (2 work, 0 fix). It merged on 2026-11-04 as master 2a36a674, armed on fabric-coordinator's AUTHORIZES 01a1a5ef: build.rs is a security boundary, minimum 8. git fetch over ssh failed about 3 times in 4 that day; `fabric-pr arm` refuses to count until a fetch succeeds, so retry it in a loop. A GitHub 502 on the merge left the PR unarmed with the marker posted, and a rerun of arm merged it.

*References: attach-pane-scroll-bar, herdr-restart-loses-moveto-agents*

*Anchors: `src/server/terminal_attach.rs::attach_layout`, `agent-fabric:runtime/provisioning/moveto/moveto.py::HARNESS_SESSION`*

*Observed 2026-11-04 (rust-ui-dev)*
