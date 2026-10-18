---
role: "python-dev"
class: index
description: "What python-dev knows and where it lives."
tier: 1
distilled_at: "2026-10-18"
---

# python-dev — knowledge index

A session is given the charter and brief (in the launch prompt),
and the project's remit with a pointer to this index (from the
session-start hook) — nothing below. Open a slice when its cue
matches what you are doing; a `workflow` slice says how a kind of
work is done here, so read the matching ones before that work.
Paths are relative to this working copy; `../agent-fabric/` is the
control plane checked out beside it.

## charter

- [`../agent-fabric/identities/roles/python-dev/charter.md`](../agent-fabric/identities/roles/python-dev/charter.md) — The fleet's Python developer: command-line tools, services and their tests, written to a frozen contract on the standard library, and the port of shell scripts to Python with the old tests as the parity oracle.

## brief

- [`../agent-fabric/identities/roles/python-dev/brief.md`](../agent-fabric/identities/roles/python-dev/brief.md) — How python-dev works day to day, in any project: freeze the contract, keep boundaries and failure explicit, prove the oracle can fail, verify the real invocation path, deliver evidence by level.

## domain

- [`../agent-fabric/memory/domains/python-dev/domain/bounded-subprocess-three-seams.md`](../agent-fabric/memory/domains/python-dev/domain/bounded-subprocess-three-seams.md) — A subprocess with a timeout fails at three seams reviewers keep finding — TimeoutExpired uncaught at the entry, a kill that reaches only the wrapper, a bound printed from exc.timeout (3.12 reports the time left)
- [`../agent-fabric/memory/domains/python-dev/domain/codeql-sarif-shows-the-flow.md`](../agent-fabric/memory/domains/python-dev/domain/codeql-sarif-shows-the-flow.md) — a CodeQL alert you cannot explain — fetch the analysis SARIF; its codeFlows name the exact source (often a name heuristic on a constant)
- [`../agent-fabric/memory/domains/python-dev/domain/dead-pid-fixture-must-exceed-pid-max.md`](../agent-fabric/memory/domains/python-dev/domain/dead-pid-fixture-must-exceed-pid-max.md) — a test's "dead" pid must be 2**22 + 1 or more; 999999 or 2**22 - 5 can be live on a long-running host (pid_max 4194304)
- [`../agent-fabric/memory/domains/python-dev/domain/decrypt-only-what-you-use.md`](../agent-fabric/memory/domains/python-dev/domain/decrypt-only-what-you-use.md) — code that reads a store of secrets in bulk, or decodes a decrypted value — read only the names used; a decode error's message quotes the bytes
- [`../agent-fabric/memory/domains/python-dev/domain/download-deadline-watchdog.md`](../agent-fabric/memory/domains/python-dev/domain/download-deadline-watchdog.md) — Bounding a urllib download by wall-clock time (gateway-install, #176): read() and readline do not honour a deadline; use a watchdog that shuts down a duplicated socket
- [`../agent-fabric/memory/domains/python-dev/domain/env-isolation-in-process-environ.md`](../agent-fabric/memory/domains/python-dev/domain/env-isolation-in-process-environ.md) — an oracle's git/env isolation set in a filtered env dict misses fixture calls that pass no env=; set it in os.environ and prove it with a hostile caller config
- [`../agent-fabric/memory/domains/python-dev/domain/exec-inherits-python-ignored-signals.md`](../agent-fabric/memory/domains/python-dev/domain/exec-inherits-python-ignored-signals.md) — a Python wrapper that os.exec's a command, or a test that probes signal dispositions — SIGPIPE/SIGXFSZ are SIG_IGN after Python start-up
- [`../agent-fabric/memory/domains/python-dev/domain/facade-split-monkeypatch-trap.md`](../agent-fabric/memory/domains/python-dev/domain/facade-split-monkeypatch-trap.md) — before splitting a Python module behind a re-exporting facade, find every patch of its attributes — including inside subprocess code strings and by-path loads
- [`../agent-fabric/memory/domains/python-dev/domain/gh-pr-checks-required-plain-text.md`](../agent-fabric/memory/domains/python-dev/domain/gh-pr-checks-required-plain-text.md) — gh pr checks with nothing to list prints one stderr line and exits 1, even with --json; two texts; gh.no_checks_reported recognises them
- [`../agent-fabric/memory/domains/python-dev/domain/git-config-get-reads-beyond-the-repo.md`](../agent-fabric/memory/domains/python-dev/domain/git-config-get-reads-beyond-the-repo.md) — Reading trust state from a repo's .git/config — a plain `git config --get` also reads ~/.gitconfig, system and GIT_CONFIG_* env; use --local, and keep every other reader of the state in agreement
- [`../agent-fabric/memory/domains/python-dev/domain/git-fixture-maintenance-lock.md`](../agent-fabric/memory/domains/python-dev/domain/git-fixture-maintenance-lock.md) — a fixture git commit can start detached maintenance holding objects/maintenance.lock, so a before/after digest of the repo differs about once in thirty runs
- [`../agent-fabric/memory/domains/python-dev/domain/js-python-parity-at-boundaries.md`](../agent-fabric/memory/domains/python-dev/domain/js-python-parity-at-boundaries.md) — porting Node to Python where both must answer alike — the JavaScript semantics Python gets wrong by default (JSON, strings, numbers, argv, keys, time bounds)
- [`../agent-fabric/memory/domains/python-dev/domain/mutation-pyc-stale-same-second.md`](../agent-fabric/memory/domains/python-dev/domain/mutation-pyc-stale-same-second.md) — Mutation runs that edit a source and rerun within the same second can run a stale .pyc - clear __pycache__ and set PYTHONDONTWRITEBYTECODE
- [`../agent-fabric/memory/domains/python-dev/domain/mutation-run-read-rc-not-fail-count.md`](../agent-fabric/memory/domains/python-dev/domain/mutation-run-read-rc-not-fail-count.md) — planting a mutation and counting FAIL lines passes when the test crashes or the fixture is dangling — read rc and use symlink targets that exist
- [`../agent-fabric/memory/domains/python-dev/domain/no-token-case-needs-root-and-ceiling.md`](../agent-fabric/memory/domains/python-dev/domain/no-token-case-needs-root-and-ceiling.md) — a "no token" test needs a scratch cwd AND a scratch AGENT_FABRIC_ROOT AND a git ceiling; cwd alone leaves the workspace bridge-token
- [`../agent-fabric/memory/domains/python-dev/domain/openssl-ed25519-pkeyutl-measured.md`](../agent-fabric/memory/domains/python-dev/domain/openssl-ed25519-pkeyutl-measured.md) — openssl pkeyutl Ed25519 from Python — key via /dev/fd pipe works, message must be a regular file (one-shot), DER store forms read directly; CI images lack openssl; ~9 ms/sign
- [`../agent-fabric/memory/domains/python-dev/domain/oracle-blind-spots-in-ports.md`](../agent-fabric/memory/domains/python-dev/domain/oracle-blind-spots-in-ports.md) — Porting a script with its old test as the oracle — the shapes of mutation an oracle passes, and how each was pinned
- [`../agent-fabric/memory/domains/python-dev/domain/pgrep-wait-loop-matches-itself.md`](../agent-fabric/memory/domains/python-dev/domain/pgrep-wait-loop-matches-itself.md) — an until-pgrep -f wait loop whose pattern is in its own command line never ends
- [`../agent-fabric/memory/domains/python-dev/domain/process-group-test-zombie-pid1.md`](../agent-fabric/memory/domains/python-dev/domain/process-group-test-zombie-pid1.md) — a "grandchild was killed" test that uses os.kill(pid,0) fails in containers whose PID 1 does not reap; read /proc state Z and poll
- [`../agent-fabric/memory/domains/python-dev/domain/python-defaults-that-differ-from-node.md`](../agent-fabric/memory/domains/python-dev/domain/python-defaults-that-differ-from-node.md) — porting Node to Python — the stdlib defaults that silently differ (Unicode \d, or vs ??, urllib proxy/redirect, header CRLF errors, stdout encoding)
- [`../agent-fabric/memory/domains/python-dev/domain/reading-git-objects-under-a-hostile-git-dir.md`](../agent-fabric/memory/domains/python-dev/domain/reading-git-objects-under-a-hostile-git-dir.md) — reading signed content from a repo whose .git the agent owns - replace refs, loose objects, grafts, commit-graph, what a mutation test must pin
- [`../agent-fabric/memory/domains/python-dev/domain/regex-redos-fix-needs-old-new-comparison.md`](../agent-fabric/memory/domains/python-dev/domain/regex-redos-fix-needs-old-new-comparison.md) — Narrowing a regex to stop backtracking in a refusing validator changes what it accepts; compare old and new exhaustively and pin nested/unbalanced must-refuse cases
- [`../agent-fabric/memory/domains/python-dev/domain/relay-text-and-state-file-hazards.md`](../agent-fabric/memory/domains/python-dev/domain/relay-text-and-state-file-hazards.md) — writing a record from GZCoord relay text or appending under the agent lock - lone surrogates, FIFOs, and what a reviewer leaves in TMPDIR
- [`../agent-fabric/memory/domains/python-dev/domain/review-before-suite-and-numeric-guards.md`](../agent-fabric/memory/domains/python-dev/domain/review-before-suite-and-numeric-guards.md) — ordering a delivery's checks (review, then the full suite) and guarding numbers parsed from JSON or argv in Python
- [`../agent-fabric/memory/domains/python-dev/domain/role-env-strips-git-vars.md`](../agent-fabric/memory/domains/python-dev/domain/role-env-strips-git-vars.md) — a test's role env built from os.environ must drop inherited GIT_*; prove with GIT_DIR at a decoy repo and a hostile GIT_CONFIG_GLOBAL
- [`../agent-fabric/memory/domains/python-dev/domain/shell-text-secrets-and-git-answers.md`](../agent-fabric/memory/domains/python-dev/domain/shell-text-secrets-and-git-answers.md) — porting a shell read or a git check — a token in a child's argv is readable in /proc; rev-parse answers false with exit 0; unknown git state is not clean
- [`../agent-fabric/memory/domains/python-dev/domain/splitting-a-closure-heavy-main.md`](../agent-fabric/memory/domains/python-dev/domain/splitting-a-closure-heavy-main.md) — splitting a long Python main() of nested closures into modules - state object first, then byte-identical moves a verifier proves; survivors checked on the base
- [`../agent-fabric/memory/domains/python-dev/domain/stand-in-relay-listener-and-home.md`](../agent-fabric/memory/domains/python-dev/domain/stand-in-relay-listener-and-home.md) — proving a hook never reaches the relay: a local listener recording request lines, an empty HOME, shutdown() before close(); a branch behind main fails fresh_git/launch_cli
- [`../agent-fabric/memory/domains/python-dev/domain/status-sentinel-collides-with-read-state.md`](../agent-fabric/memory/domains/python-dev/domain/status-sentinel-collides-with-read-state.md) — deriving an outcome string from a remote state (state.lower()) and testing it against a success sentinel — the read value can BE the sentinel
- [`../agent-fabric/memory/domains/python-dev/domain/test-process-identity-cross-talk.md`](../agent-fabric/memory/domains/python-dev/domain/test-process-identity-cross-talk.md) — a test that finds "its" processes by command line kills and counts another concurrent run's; identify by a per-run env token, prove with decoys
- [`../agent-fabric/memory/domains/python-dev/domain/test-stamps-taken-by-fake-at-write-time.md`](../agent-fabric/memory/domains/python-dev/domain/test-stamps-taken-by-fake-at-write-time.md) — a timestamp a test composes before launching the code under test is raced by host load; let the fake stamp it when it writes
- [`../agent-fabric/memory/domains/python-dev/domain/text-true-folds-crlf-review-claim-unobservable.md`](../agent-fabric/memory/domains/python-dev/domain/text-true-folds-crlf-review-claim-unobservable.md) — subprocess text=True turns CRLF into LF, so a "split before replace \r" review finding on gh output is not observable; non-exec fake needs PATH without a later real binary
- [`../agent-fabric/memory/domains/python-dev/domain/typeddict-notrequired-under-future-annotations.md`](../agent-fabric/memory/domains/python-dev/domain/typeddict-notrequired-under-future-annotations.md) — typing a dict-convention record in this fabric — NotRequired is silently required under `from __future__ import annotations`; hold each type to real values by test
- [`../agent-fabric/memory/domains/python-dev/domain/verify-incoming-needs-head-behind.md`](../agent-fabric/memory/domains/python-dev/domain/verify-incoming-needs-head-behind.md) — running the store's _verify_incoming on a fresh clone passes vacuously because HEAD already is the tip; set HEAD to the base and keep a refusing control before reporting "passes"
- [`../agent-fabric/memory/domains/python-dev/domain/verify-status-from-stderr-is-forgeable.md`](../agent-fabric/memory/domains/python-dev/domain/verify-status-from-stderr-is-forgeable.md) — parsing [GNUPG:] lines from git verify-commit --raw stderr — git's own error quotes the signature header; gate on exit 0

## intersection

- [`.agent-fabric/memory/shared/intersection-fleet-deck-attention-seam.md`](.agent-fabric/memory/shared/intersection-fleet-deck-attention-seam.md) — FleetDeck's "needs you" views read agent-fabric fleet.py's derived `attention` section — who owns which half of the seam, and where its shape is authoritative (shared)

## recall

- [`../agent-fabric/identities/roles/python-dev/recall.md`](../agent-fabric/identities/roles/python-dev/recall.md) — Where python-dev's knowledge lives — charter, remit, distilled slices, this agent's memory — and how to trace a claim to its sources.
