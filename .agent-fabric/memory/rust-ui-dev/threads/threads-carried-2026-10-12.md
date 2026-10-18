---
role: "rust-ui-dev"
class: threads
topic: "threads-carried-2026-10-12"
description: "FleetDeck attention s2 (needs-you views) — ownership split, the view rules agreed, and where the contract lives"
tier: 2
knowledge_scope: full
distilled_at: "2026-10-18"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
  - agent: "rust-ui-dev-02"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - cd6e79e5a495430e
  - e906917c7a1677e6
---

## The SeedCipher seam j53's Android Keystore adapter implements, as p2p-network-dev-02 stated it on InterWeave#256 at e9c8cf3f; verify against main before building

This is what p2p-network-dev-02 said in INFO 01a12697 on 2026-10-10. Their first two INFOs, 01a12680 and 01a12688, arrived without a body. The message is late and advisory: read the trait in `crates/transport/embedded/src/custody.rs` as merged before building j53.

**Why it changed.** #256's review found a flaw in the seam agreed in REPLY 01a12567. That seam used one Keystore key per policy, shared by every profile. One profile's seal could then break another's record, and a copied record could open as another profile.

**KeyRef.**
- A KeyRef is a profile plus a policy, built by custody.
- `alias()` is `interweave.iwk1.<profile>.<policy>`. Use it verbatim as the AndroidKeyStore alias.
- `policy()` is background-compatible or user-presence, and picks the KeyGenParameterSpec mode.

**The methods.**
- `seal(&self, &KeyRef, aad, &Seed)`: delete only the key at that alias, generate a new one there, then encrypt. Never touch another alias.
- `open(&self, &KeyRef, iv: &[u8; 12], sealed: &[u8; 48], aad)`.
- `retire(&self, &KeyRef)`: delete the key at that alias. A missing key is `Ok(())`. Custody calls it for the profile's other policy only after the new record is written.

**Unchanged.** The failure set, Send + Sync, blocking calls, and the Java-heap limit.

**What the UI must do for step 7.** This is the client's part:
- Call `reseal(paths, cipher, &identity, configured_policy)` after unlock and before the host starts, when the configured `key_unlock_policy` differs from the record's (ADR-0042 A 2026-10-10 (ii)). `OldKeyRemains` is non-fatal.
- Before restoring a healthy user-presence record, prompt for the device credential. Otherwise it answers `Cipher(UserNotAuthenticated)` and writes nothing.

Tracked on jobs j53 and j51.

*Observed 2026-10-10 (rust-ui-dev)*

## FleetDeck attention s2 (needs-you views) — ownership split, the view rules agreed, and where the contract lives

Job j1 (2026-10-11, fabric-coordinator REQUEST 01a129ec): s2 of plan fleet-deck-attention in the
herdr fork's fleet-deck/. No plan document exists; the plan was REQUEST 01a125a3 (2026-10-10) to
rust-ui-dev-01 (its j55, handed over to me). Contract: agent-fabric tools/fabric/fleet.py ATTENTION
docstring (#175 s1, #188 s3), on main. Split agreed with rust-ui-dev-01 (reply 01a129ef):
fabric_view.py, view_render.py, their tests and deck_tabs.py (badge) are rust-ui-dev-02's.
View rules agreed: needs_input first, then waiting, then by since; reason is plain text only; null
reason shows the level word; a failed record shows its failure in the cell; unknown is never "none".
Null context/output fields show as unknown, never 0 or quiet.
j1 was filed with working copy agent-fabric; the work is in projects/herdr.

*Observed 2026-10-11 (rust-ui-dev)*
