"""fabric_view snapshot: each view printed as text, read afresh, every row.

fleet.py is a fake here that answers each section with test_view_render's
fixture records (fleet.py's shape), so a snapshot goes through the views'
own Fetcher, Store and renderers exactly as a pane does.
"""

import io
import threading
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace

import fabric_view as fv
import report_render as rr
import view_render as vr
from test_view_render import FULL, PROC, ok

# The board's, the agent view's and compare's sections, and plans.
TTLS = {"states": 5, "presence": 30, "proc": 5, "jobs": 30, "closed_jobs": 60, "prs": 120,
        "usage": 60, "host": 30, "tokens": 600, "plans": 60}
PLANS = ok("fabric-plan", "2026-10-14T06:00:00Z", {"login": "user", "plans": [
    {"id": "p1", "title": "fleet-deck snapshot", "steps": [
        {"id": "s1", "owner": "rust-ui-dev-02", "title": "snapshot command", "state": "doing", "after": []}]}]})
WATCHED = {**PROC, "data": {**PROC["data"], "inbox_watch": True}}


class FakeFleet:
    """fleet.py's surface the views use: SECTIONS, load_placements, roots,
    fetch and attention_record."""

    def __init__(self, fail=(), hold=None, placements_fail=False):
        self.SECTIONS = {s: SimpleNamespace(ttl=ttl, derives=()) for s, ttl in TTLS.items()}
        self.SECTIONS["attention"] = SimpleNamespace(ttl=0, derives=("states", "jobs"))
        self.roots = SimpleNamespace(engine_root=lambda: "/af")
        self.fail = set(fail)
        self.hold = hold or {}          # section -> Event the fetch waits on
        self.placements_fail = placements_fail
        self.asked = []

    def load_placements(self, root):
        if self.placements_fail:
            raise FileNotFoundError("/af/runtime/hosts/registry.json")
        return {login: SimpleNamespace(host="develop-qzapp", kind="agent")
                for login in ("architect-cto-01", "rust-ui-dev-02")}

    def fetch(self, sections, agent, max_age, days=None):
        (s,) = sections
        self.asked.append((s, agent, max_age, days))
        if s in self.hold:
            self.hold[s].wait(10)
        if s in self.fail:
            raise RuntimeError(f"{s}: fabric-ctl refused")
        if s == "plans":
            return {"agents": [], "plans": PLANS}
        logins = [agent] if agent else list(self.load_placements("/af"))
        rec = WATCHED if s == "proc" else FULL[s]
        doc = {"agents": [{"login": login, "sections": {s: rec}} for login in logins]}
        if s == "prs":
            doc["prs_unplaced"] = ok("pr-gate", "2026-10-09T11:01:00Z", {"prs": []})
        return doc

    @staticmethod
    def attention_record(states, jobs, now):
        return ok("derived:states+jobs", states.get("at"), {"level": "none", "reason": None, "since": None})


def snap(fleet, screen, login=None, width=140, metric=0, wait_s=10.0):
    return fv.snapshot_text(fv.snapshot_lines(fleet, screen, login, width, metric, wait_s=wait_s)).splitlines()


class Views(unittest.TestCase):
    def test_board_has_the_panes_title_and_columns_and_every_row(self):
        fleet = FakeFleet()
        lines = snap(fleet, "board")
        self.assertTrue(lines[0].startswith("Fleet · 0 of 2 need you · snapshot · oldest value "), lines[0])
        self.assertEqual(lines[1].split(), " ".join(c.title for c in vr.BOARD_COLUMNS).split(),
                         "every column the pane has, in its order")
        rows = [t for t in lines if t.startswith("  architect-cto-01") or t.startswith("  rust-ui-dev-02")]
        self.assertEqual(len(rows), 2)
        self.assertFalse(any(t.startswith(">") for t in lines), "a snapshot selects no row")
        self.assertTrue(all(t == t.rstrip() for t in lines))
        self.assertEqual({s for s, *_ in fleet.asked}, set(vr.BOARD_SECTIONS) - {"attention"},
                         "every section the board shows, once; attention told from states and jobs")
        self.assertTrue(all(max_age is None for _, _, max_age, _ in fleet.asked),
                        "each section's own TTL, as a pane's first read")

    def test_agent_is_the_enter_view_with_its_inbox_watch(self):
        fleet = FakeFleet()
        lines = snap(fleet, "agent", "rust-ui-dev-02", width=100)
        self.assertTrue(lines[0].startswith("rust-ui-dev-02 · snapshot · "), lines[0])
        self.assertIn("  inbox watch running", lines)
        self.assertEqual(lines[-1], vr.AGENT_KEYS)
        self.assertEqual({a for _, a, _, _ in fleet.asked}, {"rust-ui-dev-02"})
        self.assertIn(("tokens", "rust-ui-dev-02", None, fv.TOKENS_DAYS), fleet.asked)

    def test_compare_shows_the_chosen_metric(self):
        lines = snap(FakeFleet(), "compare", metric=1)
        self.assertTrue(lines[0].startswith(f"Compare · {rr.METRICS[1].title} · snapshot"), lines[0])
        self.assertTrue(any(f"[2 {rr.METRICS[1].title}]" in t for t in lines))

    def test_plan_shows_each_plan(self):
        lines = snap(FakeFleet(), "plan")
        self.assertTrue(lines[0].startswith("Plans · snapshot"), lines[0])
        self.assertTrue(any("snapshot command" in t for t in lines))

    def test_prs_lists_every_owner(self):
        lines = snap(FakeFleet(), "prs")
        self.assertTrue(lines[0].startswith("Pull requests in flight · 2 · snapshot"), lines[0])
        self.assertEqual(sum(1 for t in lines if t.startswith("    #9")), 2, "both agents' PR, none cut")


class Failures(unittest.TestCase):
    def test_a_section_that_fails_alone_is_drawn_as_the_pane_draws_it(self):
        lines = snap(FakeFleet(fail={"jobs"}), "board")
        self.assertTrue(any(t.startswith("? jobs not read") and "fabric-ctl refused" in t for t in lines))

    def test_nothing_read_at_all_is_an_error_not_a_board_of_question_marks(self):
        with self.assertRaises(fv.SnapshotError) as e:
            fv.snapshot_lines(FakeFleet(fail=set(TTLS)), "board", None, 140)
        self.assertIn("no section could be read", str(e.exception))

    def test_an_unreadable_registry_is_an_error(self):
        with self.assertRaises(fv.SnapshotError):
            fv.snapshot_lines(FakeFleet(placements_fail=True), "board", None, 140)

    def test_an_unplaced_login_is_refused(self):
        with self.assertRaises(LookupError):
            fv.snapshot_lines(FakeFleet(), "agent", "nobody", 140)

    def test_a_section_still_reading_at_the_wait_is_said_not_awaited(self):
        gate = threading.Event()
        try:
            lines = snap(FakeFleet(hold={"tokens": gate}), "board", wait_s=0.3)
        finally:
            gate.set()
        self.assertIn("· reading tokens", lines[0])


class Command(unittest.TestCase):
    def run_main(self, args, env):
        err = io.StringIO()
        with redirect_stderr(err):
            try:
                code = fv.snapshot_main(args, env)
            except SystemExit as e:     # argparse's usage refusal
                code = e.code
        return code, err.getvalue()

    def test_usage_is_exit_2(self):
        self.assertEqual(self.run_main(["agent"], {})[0], 2)
        self.assertEqual(self.run_main(["board", "alice"], {})[0], 2)
        self.assertEqual(self.run_main(["compare", "--metric", "9"], {})[0], 2)
        self.assertEqual(self.run_main(["board", "--width", "5"], {})[0], 2)

    def test_fleet_deck_snapshot_is_this_command(self):
        import fleet_deck
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as e:
            fleet_deck.main(["snapshot", "agent"])
        self.assertEqual(e.exception.code, 2)
        self.assertIn("a login goes with agent", err.getvalue())

    def test_no_fleet_py_is_exit_1_with_one_line(self):
        code, err = self.run_main(["board"], {"AGENT_FABRIC_ROOT": "/nonexistent"})
        self.assertEqual(code, 1)
        self.assertEqual(len(err.splitlines()), 1)
        self.assertIn("has no fleet.py", err)


if __name__ == "__main__":
    unittest.main()
