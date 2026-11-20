---
role: "fabric-coordinator"
class: index
description: "What fabric-coordinator knows and where it lives."
tier: 1
distilled_at: "2026-11-17"
---

# fabric-coordinator — knowledge index

A session is given the charter and brief (in the launch prompt),
and the project's remit with a pointer to this index (from the
session-start hook) — nothing below. Open a slice when its cue
matches what you are doing; a `workflow` slice says how a kind of
work is done here, so read the matching ones before that work.
Paths are relative to this working copy; `../agent-fabric/` is the
control plane checked out beside it.

## charter

- [`../agent-fabric/identities/roles/fabric-coordinator/charter.md`](../agent-fabric/identities/roles/fabric-coordinator/charter.md) — Owns the control plane: agent-fabric's role definitions, catalogue, routing policy, authority rules and the GZCoord protocol; the only role that changes what other roles are.

## brief

- [`../agent-fabric/identities/roles/fabric-coordinator/brief.md`](../agent-fabric/identities/roles/fabric-coordinator/brief.md) — How fabric-coordinator works day to day: the control plane's only writer — roles, routing, policy, the protocol, the launch — changed in small verified commits, distributed to every account, never project truth.

## solution

- [`.agent-fabric/memory/fabric-coordinator/solution/deck-boot-summary-not-in-deck-log.md`](.agent-fabric/memory/fabric-coordinator/solution/deck-boot-summary-not-in-deck-log.md) — fleet-deck start --auto prints its "up: N; skipped" boot summary to its own terminal, not deck.log; use presence instead
- [`.agent-fabric/memory/fabric-coordinator/solution/harness-pane-enter-lost-at-start.md`](.agent-fabric/memory/fabric-coordinator/solution/harness-pane-enter-lost-at-start.md) — after a reboot or unit restart, an account's harness pane can sit at a bare shell instead of moveto's --wait prompt, so fleet-deck start --auto activates nothing

## workflow

- [`.agent-fabric/memory/fabric-coordinator/workflow/arm-refused-ruleset-lacks-fabric-armed.md`](.agent-fabric/memory/fabric-coordinator/workflow/arm-refused-ruleset-lacks-fabric-armed.md) — fabric-pr arm refuses on a repo whose ruleset predates ADR-019 A 2026-11-01 (no fabric/armed required check); applying it is the owner's decision (j551)
- [`.agent-fabric/memory/fabric-coordinator/workflow/deck-build-distribution-is-owners-command.md`](.agent-fabric/memory/fabric-coordinator/workflow/deck-build-distribution-is-owners-command.md) — how a merged herdr fleet-deck change reaches the operator deck: ff the shared checkout and run its fleet-deck/install, the owner's command from a terminal
- [`.agent-fabric/memory/fabric-coordinator/workflow/deck-live-readback-recipe.md`](.agent-fabric/memory/fabric-coordinator/workflow/deck-live-readback-recipe.md) — how to read back fleet deck attach behaviour live on the operator deck (tab focus, tabs setting, ssh counts) without miscounting
- [`.agent-fabric/memory/fabric-coordinator/workflow/review-next-needs-card-base.md`](.agent-fabric/memory/fabric-coordinator/workflow/review-next-needs-card-base.md) — fabric-review next refuses a round-1 request whose range base is a ref name (origin/master) until card_base is set

## recall

- [`../agent-fabric/identities/roles/fabric-coordinator/recall.md`](../agent-fabric/identities/roles/fabric-coordinator/recall.md) — How to ask the control plane about itself: status, routing, lint, migration records.
