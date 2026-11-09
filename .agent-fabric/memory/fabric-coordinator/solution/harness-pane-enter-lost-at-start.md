---
role: "fabric-coordinator"
class: solution
topic: "harness-pane-enter-lost-at-start"
description: "after a reboot or unit restart, an account's harness pane can sit at a bare shell instead of moveto's --wait prompt, so fleet-deck start --auto activates nothing"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: user
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - b7e34e552c25b874
---

## after a reboot or unit restart, an account's harness pane can sit at a bare shell instead of moveto's --wait prompt, so fleet-deck start --auto activates nothing

On 2026-10-31, after a host reboot, `fleet-deck start --auto` in attach mode
brought up no session. The deck attached each account and found a bare shell
(`[<login>@develop-qzapp projects]$`) where moveto's `<login> - Enter to activate`
prompt should be. It skipped each account after PROMPT_WAIT_S (45 s).

Cause: the `ensure` step of agent-fabric-harness.service
(tools/fabric/control/harness_pane.py) types the enter line with `pane run`
into a pane whose shell is not yet reading input. The line is lost, and ensure
still exits 0. Measured: 18 of 29 units at boot; on one-by-one restarts, 6 of
18 failed, then 2 of 6, then 0.

Workaround: `fabric-ctl <login> harness-stop` then `harness-start` for every
login that has no `moveto.py … --wait` process (`ps -eo user:22,args`).
Repeat until none is missing, then run `fleet-deck start --auto` again.

The fix is python-dev's (they wrote harness_pane.py). Queued as job j513.

Root cause (measured on throwaway servers): a restored pane's bash is still
sourcing /etc/profile.d (flatpak, grepconf.sh, readlink) when ensure asks, and
running_program() took any non-shell pid for a session, so it typed nothing.
Fixed in agent-fabric PR #443 (66324c90): settle window and read-back.

A second fault blocked the same boot until 2026-10-31: fleet-deck's
DeckFleet.waiting read the prompt with `pane read --source recent`, which comes
back empty on an attached pane, so start --auto in attach mode pressed nobody.
Reported to rust-ui-dev-01 (OBSERVATION 01a193ea-c676-7012-a98d-38b40654e0b9);
fixed in herdr fork commit 6b12fbec: waiting reads `--source visible` for an
attach (`fleet-deck/fleet_deck.py::waiting`). No Enter by hand is needed.

*Anchors: `agent-fabric:tools/fabric/control/harness_pane.py::def ensure`, `fleet-deck/boot.py::PROMPT_WAIT_S`, `fleet-deck/fleet_deck.py::waiting`*

*Observed 2026-11-09 (fabric-coordinator)*
