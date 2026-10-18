---
role: "rust-ui-dev"
class: solution
topic: "ssh-pane-endpoint-match"
description: "How the deck links an ssh harness pane to its session (ssh_client vs the pane's own socket), and why an agent login cannot run the live check"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 10cd45185f5417e1
---

## How the deck links an ssh harness pane to its session (ssh_client vs the pane's own socket), and why an agent login cannot run the live check

FleetDeck #32 (j14, request 01a13e87): an ssh pane (Moveto.via == SSH) has a harness when a live
session's stream `ssh_client` {addr, port} (sshd's SSH_CLIENT, recorded by enter-ssh) equals the
local end of an ESTABLISHED TCP socket of the pane's own ssh pid (`proc_ssh_endpoints` in
fleet-deck/fabric_deck.py: /proc/<pid>/fd socket inodes → that pid's net/tcp, tcp6).
`deck_tabs.endpoint` normalises: v4-mapped v6 → v4, IPv6 zone dropped. No end read (ProxyJump,
ControlMaster client, mid-connect) → old rule (live >= 1 is the pane's).
- A stale record already displays "stale", so a test of the freshness guard must assert
  `deck.tracks[login].state`, not the panel reports — a report-only test let the mutant live.
- The live check needs the operator's deck key (~/.ssh/fabric_deck); agent logins have none, so
  the operator (develop-qzapp/user) runs it and sends the result.
- Merge only after the State field producer (python-dev-04) merged: without the field every
  readable ssh pane with a live session reads running elsewhere.

*Anchors: `fleet-deck/fabric_deck.py::proc_ssh_endpoints`, `fleet-deck/fabric_deck.py::ssh_harness`, `fleet-deck/deck_tabs.py::endpoint`*

*Observed 2026-10-15 (rust-ui-dev)*
