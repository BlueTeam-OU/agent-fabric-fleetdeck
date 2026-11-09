---
role: "rust-ui-dev"
class: solution
topic: "fleetdeck-stream-close-race"
description: "j191 / PR #59: why a fleet-deck stub stream outlived its test; close() vs Popen in a daemon thread; tests sweep processes by STUB_DIR in /proc environ"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - 979c8126050fc955
---

## j191 / PR #59: why a fleet-deck stub stream outlived its test; close() vs Popen in a daemon thread; tests sweep processes by STUB_DIR in /proc environ

Two separate leaks of the `fabric-ctl ... --follow` state stream, fixed on BlueTeam-OU/agent-fabric-fleetdeck#59, merged 2026-11-01 at head afc3b004 (e6809e02 deck, 9c3224bf tests; review F1 343e6066: close() holds SIGINT/SIGTERM via stops_held() across the lock wait and the reap; afc3b004 pidfd-checked kill):

- **Deck (fabric_deck.py Stream).** `close()` read `self.child` while the daemon reader thread was still inside `Popen`. It saw None, the deck exited, the thread was dropped, and the new child was orphaned. Fix: starting a child and `close()` share the `Stream.starting` lock. Under nice-19 load on every CPU, `test_stop_ends_the_controller_and_its_stream_child` caught it: 1 failure in 3 suite runs.
- **Tests (test_fleet_deck.py clean).** Cleanup killed by the lock holder and `stream.pid`. A stream spawned just before the deck was SIGKILLed had not written its pid yet. Fix: `stub_processes()` reads /proc/<pid>/environ for the test's `STUB_DIR`, and every process the test started carries it, because `spawn_detached` passes os.environ on.

Reproduction recipe: patch `test_fleet_deck.STUBS["fabric-ctl"]` to `sleep 0.5` before `echo $$`. On master, one FleetDeckTest run then leaked 9 `sleep 3600`. To detect leftovers, scan this login's /proc/*/environ for `STUB_DIR=.../fleet-deck-test-`.

Related: [[sigstop-is-asynchronous]] (load reproduces timing flakes).

*References: sigstop-is-asynchronous*

*Anchors: `fleet-deck/fabric_deck.py::starting`, `fleet-deck/test_fleet_deck.py::stub_processes`*

*Observed 2026-11-01 (rust-ui-dev)*
