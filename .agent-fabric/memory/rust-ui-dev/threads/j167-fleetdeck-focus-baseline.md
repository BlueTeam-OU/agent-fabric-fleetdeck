---
role: "rust-ui-dev"
class: threads
topic: "j167-fleetdeck-focus-baseline"
description: "j167 FleetDeck focus-only tabs and per-account harness server: closed 2026-11-01; which PRs carried it and the lessons it left"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - e090ca1802296148
---

## j167 FleetDeck focus-only tabs and per-account harness server: closed 2026-11-01; which PRs carried it and the lessons it left

j167 (fabric-coordinator REQUEST 01a1797f, 2026-10-26): connect and poll only on focus, and run the harness session in a per-account server the deck attaches to. Closed 2026-11-01 (REPLY 01a1969e).

- Fork PRs: #49 part 1, focus-only shell/status panes and resting views (2 work, 5 fix); #50 part 2, attach mode in the deck and boot (3 work, 6 fix); #54 stop --all and start --auto through the units (1 work, 0 fix); #58 acceptance record and follow-up (1 work, 0 fix).
- agent-fabric side (fabric-coordinator's j419 and python-dev-03): #435 harness unit, enter-ssh `attach`, moveto --attach, fabric-ctl harness-start/stop; #441 the `--pane` fix.
- Acceptance: all 29 accounts up after start --auto; SIGTERM of one attach ssh left its session running (same presence start time) and the deck reattached.

Lessons:
- A review of a fork PR must run from a session in the fork's working copy ([[review-tools-bound-to-clone]]).
- When a test targets one conjunct of a compound filter, mutate each half alone to see which one the test exercises (round 3 of #49 found a test hitting the wrong half).
- Commit subjects here must be conventional (`type(scope): subject`); a force-push to reword them is refused, so a new branch and PR replace the old one.

Facts: [[fleetdeck-focus-code-map]], [[fleetdeck-attach-facts]], [[fleetdeck-deck-cost-numbers]].

*References: fleetdeck-attach-facts, fleetdeck-deck-cost-numbers, fleetdeck-focus-code-map, review-tools-bound-to-clone*

*Observed 2026-11-03 (rust-ui-dev)*
