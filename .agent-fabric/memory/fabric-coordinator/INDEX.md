---
role: "fabric-coordinator"
class: index
description: "What fabric-coordinator knows and where it lives."
tier: 1
distilled_at: "2026-11-08"
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

## domain

- [`../agent-fabric/memory/domains/fabric-coordinator/domain/agent-orchestration-standard.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/agent-orchestration-standard.md) — agent-orchestration-standard (AOS-1, JS, MIT, 2 days old, 1 star): a goal+heartbeat orchestration spec, a Claude Code live dashboard plugin and a headless worker engine; not adopted; borrow the governor's 5h/7d thresholds, plan-approval…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/apache-ossie.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/apache-ossie.md) — Apache Ossie (ex Open Semantic Interchange, OSI) — vendor-neutral JSON/YAML spec for exchanging semantic models (datasets, relationships, metrics, ai_context) across BI, analytics and AI tools; what it is, its shape, its maturity
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/apm.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/apm.md) — microsoft/apm, Agent Package Manager (Python, MIT, v0.34.0 2026-10-19) — not adopted; borrow lockfile deployed-file hashes, rebuild-in-scratch drift audit, tighten-only policy merge, text vs executable trust gate
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/apostrophe-breaks-quoted-python.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/apostrophe-breaks-quoted-python.md) — An apostrophe in a comment inside a shell script's single-quoted python block silently ends the quote; bash -n passes and the failure surfaces as a runtime syntax error far from the edit
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/autonat-client-crate-facts.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/autonat-client-crate-facts.md) — What libp2p-autonat 0.15.0's v2 CLIENT actually does — measured, and contradicting several accepted documents
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/binnacle-tideos-eval-kit.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/binnacle-tideos-eval-kit.md) — binnacle / TideOS Eval Kit: MIT pure-Rust dispatcher over 15 agent-eval CLIs (error analysis → judge calibration → paired stats → CI gate → close the loop); not adopted (8 days old, 0-star tools, README-level claims, Windows-built…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/bndr.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/bndr.md) — bndr: MIT Go one-binary Linux dashboard that finds loopback HTTP dev servers via /proc/net/tcp and bridges them onto the LAN; not adopted (shared host namespace = every login's ports incl. relay/agentd/InterWeave exposed, no auth, 0…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/cliproxyapi.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/cliproxyapi.md) — router-for-me/CLIProxyAPI (MIT Go, 56.7k stars): exposes subscription OAuth logins (Claude Code, Codex, Gemini/Antigravity, Grok, Kimi, Devin) as OpenAI/Claude/Gemini APIs with multi-account round-robin; not adopted (one process holding…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/cloudflare-tsrs-upstream-sync.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/cloudflare-tsrs-upstream-sync.md) — Cloudflare/VoidZero tsrs (Rust port of TypeScript, 2026-10): production-grade players run an AI-made port kept faithful by an agent upstream-sync loop (daily diff review → tracking issues, nightly upstream test suite as a compatibility…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/deepseek-harness.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/deepseek-harness.md) — DeepSeek Harness (dsh) — DeepSeek's open-source, everything-is-a-plugin agent harness on Cordis; what it is, its shape, what maps onto the fabric (runtime adapter, Agent Teams vs GZCoord, Agent Notes vs ADRs, credentials, approval)
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/edgextract.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/edgextract.md) — edgextract (a markdown-to-knowledge-graph library): markdown -> knowledge graph with a user ontology; a local decision model answers closed yes/no per candidate (probability + cutoff: keep / review / drop); not adopted (needs Ollama + a…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/harness2.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/harness2.md) — Harness² (google-research/harness2): recursive agent harnessing — per-task Propose–Probe–Compose over 8 harness components plus a per-domain lesson library; not adoptable as a tool; borrow its lesson schema, evidence rule and component…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/headlong.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/headlong.md) — laude-institute/headlong: a Bash agent microharness (~11K lines, Apache-2.0, 1.3k stars), always thinking, one shared mind for many people, shellm RLM; not adopted; borrow a fleet panic stop, tiered trajectory compaction, ancestry for…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/kill-option-parsing.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/kill-option-parsing.md) — How bash's kill builtin and util-linux kill read options: which later words can still change the signal after kill -0, and why -- makes any operand safe
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/locale-suffixes.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/locale-suffixes.md) — The fabric's locale suffixes: ge is Georgian (language-culture-ge, script Georgian), ru Russian; German would be de — never read ge as German
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/minigraf.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/minigraf.md) — Minigraf — embedded single-file bi-temporal graph database with Datalog (Rust; Python/Node/WASM/mobile bindings), pitched as graph memory for AI agents; what it is, its limits, what it could mean for the fabric's memory corpus
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/omerta.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/omerta.md) — shcherbak-ai/omerta: an MIT pre-commit hook and CLI that fails when a value of your own .env files is staged, tracked or in git history (not patterns); not adopted; borrow a value-based check of each account's secrets.env in the commit hook
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/open-code-review.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/open-code-review.md) — alibaba/open-code-review (ocr): Go AI review CLI, Apache-2.0, very active; not adopted; borrow a narrow fact-check filter, a coverage manifest, fail-closed checkpoint markers, and pinned read tools instead of a reviewer Bash guard
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/open-ontologies.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/open-ontologies.md) — open-ontologies (Rust, MIT, 2026-03): OWL/RDF engine that certifies its inferences for an independent Lean 4 checker; Terraform-style plan/blast radius for ontology changes; MCP server. Not adopted; borrow untrusted-engine +…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/openhuman.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/openhuman.md) — OpenHuman (tinyhumansai) — Rust single-process agent harness + Tauri desktop app, GPL-3.0, "500 agents on a $10 VPS"; memory needs hosted CortexDB; not adoptable; borrow pack-per-turn recall, tool search, result handles
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/otari.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/otari.md) — mozilla-ai/otari (Apache-2.0, Python/FastAPI multi-tenant LLM gateway, 0.28, many releases a week, AI-built at high churn): not our gateway's shape or a dependency; its hybrid mode confirms our control/data split; borrow ordered attempts…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/overgraph.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/overgraph.md) — OverGraph — embedded Rust graph + vector database (LSM, mmap segments, GQL/Cypher-style, PyO3/napi bindings), pitched as AI agent memory with temporal edges and decay; early-stage; BM25 only on its roadmap; what to borrow for the fabric's…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/paparats-mcp.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/paparats-mcp.md) — paparats-mcp: self-hosted MIT MCP server for semantic code search across many repos (tree-sitter chunks, call graph, change_impact, git history per chunk, agent architectural memory) on Docker+Qdrant+llama.cpp; not adopted now (host load…
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/pr-agent.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/pr-agent.md) — PR-Agent (The-PR-Agent/pr-agent, ex-Qodo, MIT, Python): single-LLM-call PR tools /review /describe /improve /ask; diff-only with token-aware compression; not adopted as the fabric's reviewer; borrow ideas listed
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/reflection-bwrap-mounts-on-resolved-path.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/reflection-bwrap-mounts-on-resolved-path.md) — A bwrap sandbox spec (bind, mask, link) is decided on os.path.realpath against the bound roots and tested on both distro layouts through fixture root seams; deciding by the last component flipped fail-closed to fail-open on #358
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/rtk.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/rtk.md) — rtk-ai/rtk: Rust CLI proxy that rewrites agents' shell commands (git, tests, linters) to compact output via a PreToolUse hook; claims 60-90% less bash-output tokens; not adopted — measure with the P1 ledger first
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/slice-correction-attribution-writer-name.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/slice-correction-attribution-writer-name.md) — Correction for memory/shared/domain-claude-code-attribution-reminder.md: the writer bootstrap.sh runs is runtime/claude-code/user-settings.py (attribution-off.py until 2026-09-20), and it also sets showThinkingSummaries and verbose
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/software-factory-loops-graphs-harnesses.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/software-factory-loops-graphs-harnesses.md) — the "software factory" article (2026-09-11) — planning and execution loops, a dependency graph, a harness, an outer loop; what it claims and where the fabric already matches
- [`../agent-fabric/memory/domains/fabric-coordinator/domain/yamux-silent-downgrade.md`](../agent-fabric/memory/domains/fabric-coordinator/domain/yamux-silent-downgrade.md) — Tuning libp2p yamux via any setter silently swaps the muxer to vulnerable yamux 0.12.1, and cargo-deny cannot see it; InterWeave now guards it with check_yamux_muxer.sh
- [`../agent-fabric/memory/shared/domain-claude-code-attribution-reminder.md`](../agent-fabric/memory/shared/domain-claude-code-attribution-reminder.md) — The attribution key is written by runtime/claude-code/user-settings.py, run from tools/fabric/bootstrap.py (shared)

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
