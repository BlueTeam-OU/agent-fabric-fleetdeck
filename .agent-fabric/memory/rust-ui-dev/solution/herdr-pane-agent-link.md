---
role: "rust-ui-dev"
class: solution
topic: "herdr-pane-agent-link"
description: How herdr gives panes SSH_AUTH_SOCK, why panes ask for the fabric_deck passphrase, and why a registration must not live in the deck controller
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 7734bb07055d1b1b
---

## How herdr gives panes SSH_AUTH_SOCK, why panes ask for the fabric_deck passphrase, and why a registration must not live in the deck controller

herdr (fork, src/platform/ssh_agent.rs) gives every pane SSH_AUTH_SOCK=<api socket>.agent, a
symlink the server points at: the agent the SERVER inherited (if live), else one registered via
the JSON API `server.ssh_agent.register` (connection-scoped), else `<api socket>.unavailable`.
With no inherited agent and no earlier link, no link exists and panes get no SSH_AUTH_SOCK at all.
A local attach registers nothing (only the remote bridge does). So a server started from a terminal
without an agent = every moveto-over-ssh pane asks for the fabric_deck passphrase (23 prompts,
2026-10-13). Upstream drops a registration when its connection closes even if the socket still
lives (test reconnect_and_overlapping_attachments_keep_a_stable_agent_address asserts it), so a
registration held by the deck controller dies on every `fleet-deck stop/restart`; fleetdeck #28
holds it in a detached `fleet-deck hold-agent` instead, and herdr prefers a live inherited agent
over any registration (so a keyless inherited agent gets the key, not a rival).
Verified on a throwaway debug server with a real ssh-agent (fleetdeck #28).

*Observed 2026-10-13 (rust-ui-dev)*
