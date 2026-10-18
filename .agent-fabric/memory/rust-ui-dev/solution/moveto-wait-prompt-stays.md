---
role: "rust-ui-dev"
class: solution
topic: "moveto-wait-prompt-stays"
description: "After Enter, moveto --wait's prompt stays the pane's last line during the silent refresh — never read \"prompt visible\" as \"moveto ended\""
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 5b5fde041ed9ea0d
---

## After Enter, moveto --wait's prompt stays the pane's last line during the silent refresh — never read "prompt visible" as "moveto ended"

`moveto <login> --wait` prints "<login> - Enter to activate"; after Enter, the account's
refresh (git pull, bootstrap, secrets sync: up to ~80 s) prints nothing on success, and the
local `ssh ... -- --wait` (or sudo hand-off) stays the pane's foreground for the whole session.
So the prompt stays the last non-blank line with the same moveto pid. The first #28 draft read
that as "ended" and pressed Enter again into the starting harness (review P1). Rule: a press is
tied to the moveto pid; only a different pid back at the prompt (the deck re-armed --wait) is a
failure. A test fake must keep the prompt on screen after the press, or it hides this.
**How to apply:** any deck logic keyed on the pane's screen after a press (fleet-deck/boot.py).

*Observed 2026-10-13 (rust-ui-dev)*
