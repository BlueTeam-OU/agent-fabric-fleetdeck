---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-agent-signs-not-lists"
description: "How FleetDeck decides an ssh-agent holds the deck key (signature, not listing), and why the desktop keyring proxy never counts"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 7f6178e786f07340
---

## How FleetDeck decides an ssh-agent holds the deck key (signature, not listing), and why the desktop keyring proxy never counts

Since BlueTeam-OU/agent-fabric-fleetdeck#51 (merged 2026-10-30, 6cb67c97), fleet-deck/boot.py agent_state
proves HOLDS with `ssh-add -T <key>`. That command signs through the agent and reads only the key's public
half, so it never asks the passphrase. A test with a passphrase-protected key and a counting SSH_ASKPASS proves that.
An agent that lists the key and cannot sign with it is LISTS: it is passed over and is never an add target.

- The desktop keyring proxy ($XDG_RUNTIME_DIR/keyring/ssh, no dot) lists every key in ~/.ssh.
- Panes using it opened "unlock private key" dialogs (the owner, 2026-10-30).
- So keyring_proxy() makes it LISTS by its path: it is never sent a sign request, even when keyring/.ssh holds the key.
  Whether it would then sign silently was never observed.
- An inherited proxy link means a server restart (boot.RESTART_SERVER).
  fleet_deck.attach_note offers `fleet-deck restart` only for problems a registration mends.
- Known gaps: gcr-4's $XDG_RUNTIME_DIR/gcr/ssh is not recognised; another prompting agent still gets `-T`
  (a 10 s timeout, but its dialog stays open).
- start reads the server's agent from the link <api>.agent (link_target), not from the server's env.

Test harness: test_boot.ListingOnlyAgent is a stdlib AF_UNIX fake agent. It answers identities (11) with the key,
fails everything else, and counts sign requests (13). ssh-add -l sends other non-listing requests too, so count only type 13.

On this repo, `fabric-pr arm` merged at once while the Debian/Fedora/Ubuntu checks were still pending.
They are not required checks, so watch the run after the merge (`gh run watch`).
Related: [[fleet-deck-attention-seam]], [[fabric-review-next-chain]].

*References: fabric-review-next-chain, fleet-deck-attention-seam*

*Anchors: `fleet-deck/boot.py::keyring_proxy`, `fleet-deck/boot.py::RESTART_SERVER`, `fleet-deck/fleet_deck.py::attach_note`, `fleet-deck/test_boot.py::ListingOnlyAgent`*

*Observed 2026-10-30 (rust-ui-dev)*
