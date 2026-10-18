---
role: "rust-ui-dev"
class: solution
topic: "fleet-deck-snapshot"
description: "How an agent reads Fleet Deck's views as text (fleet-deck snapshot), and why a non-operator login sees ? in half the board"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - ec3802afdf501998
---

## How an agent reads Fleet Deck's views as text (fleet-deck snapshot), and why a non-operator login sees ? in half the board

`fleet-deck snapshot board|agent LOGIN|compare [--metric N]|plan|prs [--width N]` (FleetDeck PR #31, branch develop-qzapp/rust-ui-dev-02/fleet-deck/snapshot; also `fabric-view snapshot`) prints a deck view as text through the panes' own View/Fetcher/Store and renderers (`height=None` = natural height, `selected=None` = no row marked). Exit 0 / 1 (data unreadable, or every section failed) / 2 (usage, unplaced login). Use it to check a deck change rendered, instead of `pane read` on the owner's board (which may be paused, scrolled, or behind a key).

Limit: fleet.py answers jobs, usage, host, tokens only to a host operator (agent-fabric's gate), so run on an agent login those read `?` and the title says "N not known"; only the operator's login (`user`) sees the owner's full picture.

Run against a checkout: `AGENT_FABRIC_ROOT=~/projects/agent-fabric python3 -B fleet-deck/fleet-deck snapshot board` from ~/projects/herdr (the FleetDeck working copy; its default branch is master).

*Observed 2026-10-14 (rust-ui-dev)*
