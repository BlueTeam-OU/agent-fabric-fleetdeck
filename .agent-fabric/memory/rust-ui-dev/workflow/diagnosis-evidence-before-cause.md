---
role: "rust-ui-dev"
class: workflow
topic: "diagnosis-evidence-before-cause"
description: "When diagnosing a live deck miss reported by the owner, get the timestamped evidence (the operator's deck.log) and check the code or docs before naming a cause or building a fix; three claims in one thread were withdrawn"
tier: 1
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - eeeeed5e31c08f43
---

## When diagnosing a live deck miss reported by the owner, get the timestamped evidence (the operator's deck.log) and check the code or docs before naming a cause or building a fix; three claims in one thread were withdrawn

In j23 (the missed blocked alert, 2026-10-17), I sent three claims within 20 minutes and
withdrew each one:
- "the deck logs errors only": wrong, because `_show` logs every state change it reports;
- "registering PostToolUse would clear the red": wrong, because the hooks docs have no event
  at approval, only at the tool's end;
- "the state stream went silent": refuted by the operator's deck.log, where 25 accounts
  kept logging. I had already built a watchdog for it on a local branch, which I left unpushed.
What decided the case was the deck.log timestamps, from one grep that only the operator's
login can run, followed by a reproduction against an isolated debug server.

**Why:** each wrong claim cost the coordinator a read and a correction, and nearly
started a fix in the wrong place.

**How to apply:** for a live miss the owner reports, (1) ask the operator for the log lines,
giving the exact grep and what each possible answer would mean; (2) read the code path or
the vendor docs that the claim rests on; (3) only then name a cause, labelled "verified" or
"inferred". Build a fix only for a verified cause. If a log is missing, reproduce the case
instead of guessing. Details of the case: [[deck-blocked-alert-j23]].

*References: deck-blocked-alert-j23*

*Anchors: `fleet-deck/fabric_deck.py::def _show(`*

*Observed 2026-10-18 (rust-ui-dev)*
