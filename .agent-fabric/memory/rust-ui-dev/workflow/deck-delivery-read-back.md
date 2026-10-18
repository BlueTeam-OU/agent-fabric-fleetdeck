---
role: "rust-ui-dev"
class: workflow
topic: "deck-delivery-read-back"
description: "How a merged FleetDeck change reaches the owner's live deck (Python views vs Rust binary), why the operator does it, and how to write a read-back that proves something"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 31d5951cfad27e38
---

## How a merged FleetDeck change reaches the owner's live deck (Python views vs Rust binary), why the operator does it, and how to write a read-back that proves something

A merged FleetDeck PR is not on the owner's deck until the operator's login (`user`) takes it.
That login is not this one, so the deploy is a REQUEST to fabric-coordinator. Say whose
authorisation it carries, give numbered steps, and give a read-back list as its ACCEPTANCE.

- **Python under fleet-deck/ only** (views, controller): no build and no handoff. In the
  checkout the `fabric.fleet` plugin is linked to (`agent-fabric-fleetdeck plugin link
  <checkout>/fleet-deck`, ~/projects/herdr on the operator's login), run `git pull --ff-only`
  to the merge or later. Its agent-fabric checkout must hold any fleet.py field the change
  reads. Then press `q` in the fleet tab and run `fleet-deck restart`.
- **Any Rust change**: `<checkout>/fleet-deck/install` builds and does the live handoff
  (README "Install"). It is a separate step the owner chooses when to take.
- **Check the view process is new.** Once (2026-10-13), the first restart left the old
  fabric_view running, its process dated two days earlier. The coordinator ended it and
  restarted again. Compare the view process's start time, not only the screen.
- **A flag whose condition did not happen is "not seen", not verified.** Both deploys
  (2026-10-13, 2026-10-14) read back everything except "inbox off Nm", because every watch
  was up. Give each flag in the read-back a way to make it fire (a control). Or prove it on
  your own login with `fleet-deck snapshot` against data that has it ([[fleet-deck-snapshot]]).
  Leave on the owner's list only what needs the operator: jobs, usage, host and tokens read
  `?` on an agent login.
- **`fleet-deck restart` refuses inside a herdr pane**, and the owner works from inside the deck. So the
  #38 deploy's step "press q, then fleet-deck restart" could not be run as written (2026-10-16, reply
  01a14641-0de0-7f7a-b865-7a56c457b70d): the coordinator restarted the controller from its own session.
  In a deploy request, give the restart to the coordinator by name, or give a step the operator can run
  from inside the deck.
- Seen once, after #27's handoff (2026-10-14): every pane read agent=unknown, and detection
  came back within minutes. Wait before reading the agent column.

**Why:** each step runs on a login and a live board that only the operator can touch. A
read-back that cannot fail proves nothing.
**How to apply:** when your PR is merged and the owner wants it live: name the change's kind
(Python or Rust), send the steps, and send a read-back with a control for each flag.

*References: fleet-deck-snapshot*

*Anchors: `fleet-deck/README.md::plugin link <this checkout>/fleet-deck`, `fleet-deck/install`*

*Observed 2026-10-16 (rust-ui-dev)*
