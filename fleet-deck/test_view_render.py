"""view_render: the board and the agent view on fixture records.

The records have fleet.py's shape. proc, states and presence are copied
from a live `fabric-fleet --json` on develop-qzapp (2026-10-09). jobs,
closed_jobs, prs, usage, host and tokens follow the ops' code in
agent-fabric (runtime/control/jobs.mjs, ops/usage.mjs, ops/host.mjs,
pressure.mjs; tools/fabric/fleet.py's prs_read and closed_jobs_read),
because they answer only a host operator and were not read live.
"""

import datetime
import unittest

import view_render as vr

NOW = datetime.datetime(2026, 10, 9, 11, 5, 0, tzinfo=datetime.timezone.utc)


def ok(src, at, data):
    return {"status": "ok", "src": src, "at": at, "data": data}


def bad(src, why):
    return {"status": "failed", "src": src, "at": "2026-10-09T11:00:30Z", "why": why}


PROC = ok("proc-local", "2026-10-09T11:00:19Z", {"uid": 1001, "cpu_pct": 1.6, "rss_kb": 531684, "swap_kb": 244696, "procs": 18})
STATES = ok("op:states", "2026-10-09T11:00:22Z", {
    "ts": "2026-10-09T11:00:06.652Z", "role": "architect-cto", "project": "gzapp",
    "sessions": [{"session": "9c3ad185-b9c3-4607-9d12-f8ac78d0897e", "state": "idle", "since": "2026-10-09T11:00:06Z"}],
    "state": "idle", "since": "2026-10-09T11:00:06Z", "last_session": "9c3ad185-b9c3-4607-9d12-f8ac78d0897e", "resumable": True})
PRESENCE = ok("op:presence", "2026-10-09T11:00:24Z", {"presence": {
    "status": "ok", "online": True, "sessions": 1, "since": "2026-10-08T06:28:26.190Z",
    "role": "architect-cto", "project": "gzapp", "planning": False}})
JOBS = ok("op:jobs", "2026-10-09T11:00:25Z", {"jobs": {"status": "ok", "jobs": [
    {"id": "j34", "state": "blocked", "title": "Fleet Deck: one tab per agent", "project": "herdr", "topic": "herdr",
     "priority": "normal", "source": "owner", "blocked_on": "agent-fabric activation PR", "artifacts": [], "updated": "2026-10-08T17:00:00Z"},
    {"id": "j40", "state": "active", "title": "Fleet Deck R1: fabric-view board and agent overlay as a herdr plugin",
     "project": "herdr", "topic": "fleet-deck", "priority": "normal", "source": "owner", "blocked_on": None,
     "artifacts": [], "updated": "2026-10-09T10:57:46Z"},
    {"id": "j42", "state": "queued", "title": "labels", "project": "interweave", "topic": None,
     "priority": "normal", "source": "self", "blocked_on": None, "artifacts": [], "updated": "2026-10-09T09:00:00Z"}]}})
CLOSED = ok("hostexec", "2026-10-09T11:00:40Z", {"closed_total": 23, "closed": [
    {"id": "j39", "title": "sync upstream", "state": "done", "topic": "herdr", "project": "herdr", "updated": "2026-10-09T09:28:00Z"},
    {"id": "j38", "title": "duplicate sync", "state": "dropped", "topic": "herdr", "project": "herdr", "updated": "2026-10-09T07:22:00Z"}]})
PRS = ok("pr-gate", "2026-10-09T11:01:00Z", {"prs": [
    {"pr": 9, "branch": "develop-qzapp/rust-ui-dev-01/feat/fleet-views", "ahead": 4, "last_commit": "2026-10-09T11:00:00Z", "paths_total": 6},
    {"pr": "none", "branch": "develop-qzapp/rust-ui-dev-01/fix/other", "ahead": 1, "last_commit": None, "paths_total": 1}],
    "fetch_ok": True, "prs_ok": True, "base": "origin/master"})
USAGE = ok("op:usage", "2026-10-09T11:00:26Z", {"usage_status": "ok",
    "five_hour": {"utilization": 37.0, "resets_at": "2026-10-09T13:00:00Z"},
    "seven_day": {"utilization": 12.4, "resets_at": "2026-10-14T00:00:00Z"}})
HOST = ok("op:host", "2026-10-09T11:00:27Z", {"machine": {
    "status": "ok", "cpus": 8, "loadavg": [1.2, 1.0, 0.9],
    "mem_mb": {"total": 32000, "available": 12000, "swap_total": 8192, "swap_free": 6144},
    "balloon_mb": None, "disk": [], "leases": [], "top_rss": [],
    "memory_pressure": {"status": "ok", "interval_s": 60, "samples": 30, "since": "2026-10-09T10:30:00Z",
                        "last": [{"ts": "2026-10-09T11:00:00Z", "some_avg10": 0.42, "full_avg10": 0.0, "mem_available_mb": 12000}],
                        "hour": {"samples": 30, "some_avg10": None, "full_avg10": None, "mem_available_mb": None}}}})
TOKENS = ok("op:tokens", "2026-10-09T10:58:00Z", {"email": None, "role": "architect-cto", "tokens": {
    "status": "ok", "days": 7, "files": 40, "requests": {"session": 900, "subagent": 300},
    "first": "2026-10-02T08:00:00Z", "last": "2026-10-09T10:57:00Z",
    "models": {"claude-opus-5-5": {"requests": 1000, "input": 1_000_000, "cache_write": 2_000_000, "cache_read": 40_000_000,
                                   "output": 500_000, "equiv": 9_000_000, "path": "claude"},
               "deepseek/v4-pro": {"requests": 200, "input": 100_000, "cache_write": 0, "cache_read": 0, "output": 50_000,
                                   "equiv": 350_000, "path": "broker"}},
    "claude": {"requests": 1000, "input": 1_000_000, "cache_write": 2_000_000, "cache_read": 40_000_000, "output": 500_000, "equiv": 9_000_000},
    "broker": {"requests": 200, "input": 100_000, "cache_write": 0, "cache_read": 0, "output": 50_000, "equiv": 350_000},
    "ratios": {"input": 1, "cache_write": 1.25, "cache_read": 0.1, "output": 5}}})

FULL = {"states": STATES, "presence": PRESENCE, "proc": PROC, "jobs": JOBS, "closed_jobs": CLOSED,
        "prs": PRS, "usage": USAGE, "host": HOST, "tokens": TOKENS}
NOT_OPERATOR = "op:jobs: fabric-ctl jobs: fabric-ctl: develop-qzapp/rust-ui-dev-01 is not a host operator"


def fleet():
    alpha = vr.Agent("architect-cto-01", "develop-qzapp", "agent", dict(FULL))
    beta = vr.Agent("web-dev-02", "develop-qzapp", "agent", {
        "states": ok("op:states", "2026-10-09T11:00:22Z", {"sessions": [], "state": None}),
        "proc": PROC, "jobs": bad("op:jobs", NOT_OPERATOR), "closed_jobs": None,
        "prs": ok("pr-gate", "2026-10-09T11:01:00Z", {"prs": [], "fetch_ok": True, "prs_ok": True, "base": "origin/main"}),
        "usage": ok("op:usage", "2026-10-09T11:00:26Z", {"usage_status": "no-credentials"}),
        "host": None, "tokens": ok("op:tokens", "2026-10-09T10:58:00Z", {"tokens": {"status": "no-records", "days": 7}})})
    return [alpha, beta]


def status(**kw):
    base = dict(focused=True, fetching=(), now=NOW, oldest="2026-10-09T11:00:19Z", from_cache=False)
    base.update(kw)
    return vr.Status(**base)


def texts(lines):
    return [vr.line_text(line) for line in lines]


class Board(unittest.TestCase):
    def test_a_row_says_each_column_from_its_record(self):
        lines = texts(vr.board_lines(fleet(), {}, status(), 0, 140, 20))
        row = next(t for t in lines if "architect-cto-01" in t)
        for word in ("idle", "j40 Fleet Deck R1", "23/3", "519M", "2%", "43.6M", "37%", "#9 +1"):
            self.assertIn(word, row)
        self.assertTrue(row.startswith("> "), "the selected row is marked in text, not only in colour")

    def test_a_blocked_job_is_the_current_one_only_without_an_active_one(self):
        jobs = vr.open_jobs(JOBS["data"])
        self.assertEqual(vr.current_job(jobs)["id"], "j40")
        self.assertEqual(vr.job_label(vr.current_job([j for j in jobs if j["id"] != "j40"])),
                         "j34 (blocked) Fleet Deck: one tab per agent")

    def test_failed_unread_and_absent_cells_say_which_they_are(self):
        cells = vr.board_cells(fleet()[1], NOW)
        self.assertEqual(cells["job"], (vr.NOT_READ, vr.FAILED))
        self.assertEqual(cells["jobs"], (f"{vr.UNREAD}/{vr.NOT_READ}", vr.FAILED))
        self.assertEqual(cells["state"][0], "no session")
        self.assertEqual(cells["five_hour"][0], "n/a")
        self.assertEqual(cells["tokens"][0], "0")
        self.assertEqual(cells["pr"][0], vr.NONE)

    def test_a_failed_section_is_said_once_in_the_footer_with_its_why(self):
        lines = texts(vr.board_lines(fleet(), {}, status(), 0, 140, 20))
        said = [t for t in lines if t.startswith("? jobs")]
        self.assertEqual(len(said), 1)
        self.assertIn("1 agent", said[0])
        self.assertIn("not a host operator", said[0])

    def test_host_memory_and_pressure_in_the_footer(self):
        lines = texts(vr.board_lines(fleet(), {"develop-qzapp": HOST}, status(), 0, 140, 20))
        self.assertIn("develop-qzapp: memory 19.5 of 31.2 GB used swap 2.0 GB pressure some 0.4% full 0.0%", lines)

    def test_narrow_drops_the_least_needed_columns_and_keeps_agent_state_needs_you_job(self):
        for width in (60, 48):
            cols = [c.key for c, _ in vr.board_columns(fleet(), width)]
            self.assertEqual(cols, ["login", "attention", "job"], "who needs the person outlasts the rest")
            for line in texts(vr.board_lines(fleet(), {}, status(), 0, width, 20)):
                self.assertLessEqual(len(line), width)
        self.assertEqual([c.key for c, _ in vr.board_columns(fleet(), 80)][:5], ["login", "state", "attention", "waiting", "job"])
        self.assertEqual([c.key for c, _ in vr.board_columns(fleet(), 70)], ["login", "attention", "waiting", "job"],
                         "the session's word goes before another agent's wait")
        self.assertNotIn("tokens", [c.key for c, _ in vr.board_columns(fleet(), 60)])
        self.assertEqual(len(vr.board_columns(fleet(), 200)), len(vr.BOARD_COLUMNS))

    def test_a_branch_without_a_pr_is_never_a_pr_number(self):
        self.assertEqual(vr.pr_label({"prs": [{"pr": "none"}]}), "no PR")
        self.assertEqual(vr.pr_label({"prs": [{"pr": "12"}, {"pr": None}]}), "#12 +1")
        body = texts(vr.agent_body(fleet()[0], vr.Samples(), NOW, 100))
        self.assertIn("  no PR  develop-qzapp/rust-ui-dev-01/fix/other  1 ahead", body)

    def test_a_wide_window_keeps_the_numbers_near_the_name(self):
        widths = dict((c.key, w) for c, w in vr.board_columns(fleet(), 300))
        self.assertEqual(widths["job"], vr.JOB_MAX)

    def test_the_selected_row_is_reversed_whole(self):
        row = vr.board_row(fleet()[1], vr.board_columns(fleet(), 140), True, NOW)
        self.assertEqual({style for _, style in row}, {vr.SELECTED})
        self.assertIn(vr.NOT_READ, vr.line_text(row))

    def test_a_long_title_is_cut_with_a_mark(self):
        row = texts(vr.board_lines(fleet(), {}, status(), 0, 70, 20))[2]
        self.assertIn("…", row)
        self.assertLessEqual(len(row), 70)

    def test_the_selection_stays_in_view_when_rows_overflow(self):
        many = [vr.Agent(f"agent-{i:02}", "h", "agent", {}) for i in range(40)]
        lines = texts(vr.board_lines(many, {}, status(), 35, 100, 12))
        self.assertEqual(len(lines), 12)
        self.assertTrue(any(t.startswith("> agent-35") for t in lines))

    def test_the_status_line_says_live_paused_cached_and_reading(self):
        self.assertIn("live", texts([vr.status_line("Fleet", status(), 100)])[0])
        paused = texts([vr.status_line("Fleet", status(focused=False), 100)])[0]
        self.assertIn("paused: not focused", paused)
        unknown = texts([vr.status_line("Fleet", status(focused=None), 100)])[0]
        self.assertIn("paused: press a key to go live", unknown)
        cached = texts([vr.status_line("Fleet", status(from_cache=True, fetching=("jobs", "prs")), 100)])[0]
        self.assertIn("from cache, 4 min ago", cached)
        self.assertIn("reading jobs, prs", cached)

    def test_unread_cells_before_any_answer(self):
        bare = vr.Agent("x", "h", "agent", {})
        self.assertTrue(all(t == vr.UNREAD for k, (t, _) in vr.board_cells(bare, NOW).items() if k not in ("login", "jobs")))


class Stale(unittest.TestCase):
    """A stale value is fleet.py's last good one: drawn, marked `~` in its
    text (so without colour, and on the selected row), with since when and
    why where the screen says why."""

    def stale(self, rec, why="proc-local: timeout"):
        return dict(rec, status="stale", at="2026-10-09T11:00:00Z", age_s=900, why=why)

    def test_a_stale_value_is_marked_in_words_on_the_board_and_the_footer_says_whose_since_when_and_why(self):
        a = vr.Agent("arch", "h", "agent", {"proc": self.stale(PROC)})
        self.assertEqual(vr.board_cells(a, NOW)["rss"], (vr.size_kb(531684), vr.WARN))
        lines = vr.board_lines([a, vr.Agent("b", "h", "agent", {"proc": PROC})], {"h": None}, status(), 0, 140, 20)
        rows = texts(lines)
        self.assertIn(vr.size_kb(531684) + vr.STALE, next(r for r in rows if r.startswith("> arch")))  # selected
        self.assertIn("~ proc stale for arch, read 5 min ago: proc-local: timeout", rows)

    def test_stale_jobs_mark_the_closed_open_cell(self):
        a = vr.Agent("arch", "h", "agent", {"jobs": self.stale(JOBS), "closed_jobs": CLOSED})
        self.assertEqual(vr.board_cells(a, NOW)["jobs"], ("23/3", vr.WARN))
        row = texts([vr.board_row(a, vr.board_columns([a], 140), False, NOW)])[0]
        self.assertIn("23/3~", row)

    def test_a_stale_value_cut_to_its_column_keeps_its_mark(self):
        a = vr.Agent("arch", "h", "agent", {"states": self.stale(STATES), "jobs": self.stale(JOBS),
                                            "prs": self.stale(PRS)})
        cols = vr.board_columns([a], 80)
        segments = vr.board_row(a, cols, True, NOW)[1:]       # one per column, after the marker
        for (c, w), (text, _) in zip(cols, segments):
            cell = text[1:] if text.startswith(" ") else text
            self.assertEqual(vr.cells(cell), w, c.key)
            if c.key in ("state", "job", "pr"):
                self.assertTrue(cell.endswith(vr.STALE), (c.key, cell))

    def test_past_the_footers_room_stales_and_failures_are_named_apart_once_each(self):
        down = bad("op:x", "down")
        a = vr.Agent("a", "h", "agent", {"states": down, "proc": down, "jobs": down, "usage": self.stale(USAGE),
                                         "tokens": self.stale(TOKENS)})
        b = vr.Agent("b", "h", "agent", {"states": self.stale(STATES)})
        foot = vr.failure_lines([a, b], vr.BOARD_SECTIONS, 120, limit=3, now=NOW)
        rows = texts(foot)
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0].startswith("? states not read"))
        self.assertTrue(rows[1].startswith("? also not read: proc, jobs;"))
        self.assertTrue(rows[2].startswith("~ also stale: states, usage, tokens;"))
        # A section is named once per kind: states failed for a and is stale for b.
        self.assertNotIn("states", rows[1])

    def test_the_agent_view_says_a_sections_value_is_stale_and_why(self):
        a = vr.Agent("arch", "h", "agent", {"prs": self.stale(PRS, why="pr-gate: GitHub did not answer")})
        lines, _ = vr.agent_lines(a, vr.Samples(), status(), 0, 100, 60)
        rows = texts(lines)
        self.assertTrue(any(r.startswith("Pull requests") and "stale ~" in r for r in rows))
        self.assertTrue(any("~ stale: the last good value; the fresh read failed: pr-gate: GitHub did not answer" in r
                            for r in rows))

    def test_stale_without_data_is_not_a_value(self):
        self.assertIsNone(vr.ok_data({"status": "stale", "why": "x"}))
        self.assertFalse(vr.stale({"status": "stale", "why": "x"}))


class AgentView(unittest.TestCase):
    def body(self, agent, samples=None, width=100):
        return texts(vr.agent_body(agent, samples or vr.Samples(), NOW, width))

    def test_every_section_with_its_source_and_age(self):
        body = self.body(fleet()[0])
        for heading in ("Session  op:states, 4 min ago", "Resources  proc-local, 4 min ago", "Open jobs (3)  op:jobs",
                        "Closed jobs (23)  hostexec", "Pull requests  pr-gate", "Tokens, 7 days  op:tokens, 7 min ago",
                        "Usage windows  op:usage"):
            self.assertTrue(any(t.startswith(heading) for t in body), heading)

    def test_session_state_and_what_it_waits_on(self):
        body = self.body(fleet()[0])
        self.assertIn("  state idle since 11:00Z", body)
        self.assertIn("  session 9c3ad185 · resumable", body)
        self.assertIn("  waits on agent-fabric activation PR (j34)", body)
        self.assertIn("  online · 1 session(s)", body)

    def test_jobs_with_their_times(self):
        body = self.body(fleet()[0])
        self.assertTrue(any(t.startswith("  j40   active    10:57Z  Fleet Deck R1") for t in body))
        self.assertTrue(any(t.startswith("  j34   blocked   Oct 08  Fleet Deck") for t in body))
        self.assertIn("  and 21 older", body)

    def test_tokens_usage_and_prs(self):
        body = self.body(fleet()[0])
        self.assertIn("  43.6M tokens in 1.2k requests", body)
        self.assertIn("    43.5M  claude-opus-5-5", body)
        self.assertIn("  5 hours   37%  resets 13:00Z", body)
        self.assertIn("  7 days    12%  resets Oct 14", body)
        self.assertIn("  #9  develop-qzapp/rust-ui-dev-01/feat/fleet-views  4 ahead", body)

    def test_a_failed_section_says_why_in_place(self):
        body = self.body(fleet()[1])
        i = next(i for i, t in enumerate(body) if t.startswith("Open jobs"))
        self.assertIn("is not a host operator", " ".join(" ".join(body[i + 1: i + 3]).split()))
        self.assertTrue(all(len(t) <= 60 for t in self.body(fleet()[1], width=60)))
        self.assertIn("  no-credentials", body)
        self.assertIn("  no requests recorded", body)

    def test_sparklines_from_distinct_samples_only(self):
        s = vr.Samples()
        for at, rss, cpu in (("t1", 100, 1.0), ("t1", 100, 1.0), ("t2", 200, 5.0), ("t3", 150, 3.0)):
            s.add(ok("proc-local", at, {"rss_kb": rss, "cpu_pct": cpu}))
        self.assertEqual(s.at, ["t1", "t2", "t3"])
        self.assertEqual(vr.sparkline(s.rss_kb, 10), "▁█▅")
        self.assertEqual(vr.sparkline([3, 3, 3], 10), "▁▁▁")
        self.assertEqual(vr.sparkline(s.cpu_pct, 10, ascii_only=True), "_@+")

    def test_scroll_is_clamped_to_the_body(self):
        a = fleet()[0]
        lines, scroll = vr.agent_lines(a, vr.Samples(), status(), 999, 100, 10)
        self.assertEqual(len(lines), 10)
        self.assertEqual(scroll, len(vr.agent_body(a, vr.Samples(), NOW, 100)) - 7)
        self.assertTrue(texts(lines)[0].startswith("architect-cto-01 · live · "))
        self.assertEqual(texts(lines)[1], "architect-cto · gzapp · develop-qzapp")
        self.assertEqual(texts(lines)[-1], vr.AGENT_KEYS)

    def test_every_line_fits_a_narrow_overlay(self):
        for t in texts(vr.agent_lines(fleet()[0], vr.Samples(), status(), 0, 40, 60)[0]):
            self.assertLessEqual(len(t), 40)


class OtherAccountsText(unittest.TestCase):
    """Titles, branches and whys come from other accounts (the threat
    model): none may move the cursor or overflow its line."""

    def hostile(self):
        a = fleet()[0]
        jobs = [dict(j) for j in vr.open_jobs(JOBS["data"])]
        jobs[1]["title"] = "J1 fix\rFORGED\bx\nnext\x9bline"
        jobs[0]["title"] = "漢" * 60
        a.sections["jobs"] = ok("op:jobs", JOBS["at"], {"jobs": {"status": "ok", "jobs": jobs}})
        a.sections["prs"] = ok("pr-gate", PRS["at"], dict(PRS["data"], prs=[{"pr": 9, "branch": "b\r\x1b[31mred", "ahead": 1}]))
        b = fleet()[1]
        b.sections["jobs"] = bad("op:jobs", "refused\rFORGED")
        return [a, b]

    def assert_drawable(self, lines, width):
        for line in lines:
            text = vr.line_text(line)
            self.assertFalse([c for c in text if vr.unicodedata.category(c)[0] == "C"], repr(text))
            self.assertLessEqual(vr.cells(text), width, repr(text))

    def test_the_board_draws_no_control_character_and_fits_in_cells(self):
        for width in (140, 70, 40):
            self.assert_drawable(vr.board_lines(self.hostile(), {}, status(), 0, width, 20), width)
        row = texts(vr.board_lines(self.hostile(), {}, status(), 0, 140, 20))[2]
        self.assertTrue(row.startswith("> architect-cto-01"), row)
        self.assertIn("J1 fix" + vr.CONTROL + "FORGED", row)

    def test_the_agent_view_draws_no_control_character_and_fits_in_cells(self):
        for width in (100, 40):
            a = self.hostile()[0]
            self.assert_drawable(vr.agent_lines(a, vr.Samples(), status(), 0, width, 80)[0], width)
            self.assert_drawable(vr.agent_lines(self.hostile()[1], vr.Samples(), status(), 0, width, 80)[0], width)

    def test_a_wide_why_is_wrapped_by_cells_and_reaches_the_screen_whole(self):
        a = fleet()[1]
        a.sections["jobs"] = bad("op:jobs", "拒否" * 30 + " END")
        body = texts(vr.agent_lines(a, vr.Samples(), status(), 0, 40, 80)[0])
        joined = "".join(t.strip() for t in body)
        self.assertIn("拒否" * 30 + "END", joined.replace(" ", ""))
        self.assertTrue(all(vr.cells(t) <= 40 for t in body))

    def test_wrap_cells_keeps_words_and_splits_only_what_cannot_fit(self):
        self.assertEqual(vr.wrap_cells("ab cd ef", 5), ["ab cd", "ef"])
        self.assertEqual(vr.wrap_cells("ab cd ef", 5, indent="  "), ["ab cd", "  ef"])
        self.assertEqual(vr.wrap_cells("漢字漢字漢", 4), ["漢字", "漢字", "漢"])
        # A character wider than the room ends; an indent wider than the
        # width is dropped.
        self.assertEqual(vr.wrap_cells("漢", 1), ["漢"])
        self.assertEqual(vr.wrap_cells("abc def", 3, indent="    "), ["abc", "def"])
        # A character that fits the width but not beside the indent goes
        # without the indent.
        self.assertEqual(vr.wrap_cells("ab 漢", 3, indent="  "), ["ab", "漢"])
        for text, width, indent in (("ab 漢字 c", 3, "  "), ("x " * 9, 4, "  "), ("漢" * 7, 5, " ")):
            lines = vr.wrap_cells(text, width, indent)
            self.assertTrue(all(vr.cells(t) <= width for t in lines), lines)
            self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))

    def test_wide_characters_are_measured_in_cells(self):
        self.assertEqual(vr.cells("漢字ab"), 6)
        self.assertEqual(vr.cells(vr.fit("漢" * 30, 40)), 39)
        self.assertEqual(vr.cells(vr.pad("漢字", 6, right=True)), 6)


class WhysOnScreen(unittest.TestCase):
    def test_prs_that_could_not_be_listed_are_said_in_the_footer(self):
        agents = fleet()
        agents[0].sections["prs"] = ok("pr-gate", PRS["at"], dict(PRS["data"], prs_ok=False))
        lines = texts(vr.board_lines(agents, {}, status(), 0, 140, 20))
        self.assertTrue(any(t.startswith("? prs not read for 1 agent: pr-gate could not list") for t in lines))

    def test_sections_past_the_footer_are_named_with_where_their_why_is(self):
        agents = fleet()
        for name in ("jobs", "usage", "host", "tokens"):
            for a in agents:
                a.sections[name] = bad(f"op:{name}", f"{name} refused")
        lines = texts(vr.failure_lines(agents, vr.BOARD_SECTIONS, 140, limit=3))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[-1], "? also not read: host, tokens; why for tokens in each agent's view (Enter)")
        only_host = texts(vr.failure_lines(agents, ("jobs", "usage", "host"), 140, limit=2))
        self.assertEqual(only_host[-1], "? also not read: usage, host; why for usage in each agent's view (Enter)")


def attention(level, reason=None, since=None, **more):
    """fleet.py's attention record (agent-fabric tools/fabric/fleet.py, ATTENTION)."""
    data = {"level": level, "reason": reason, "since": since, "blocked": 0, "pending": 0,
            "context_pct": None, "context_at": None, "output": None}
    data.update(more)
    return ok("derived:states+jobs", "2026-10-09T11:00:22Z", data)


def agent(login, rec):
    return vr.Agent(login, "develop-qzapp", "agent", {"attention": rec})


class Attention(unittest.TestCase):
    def test_the_cell_says_the_reason_or_the_levels_word_with_its_age(self):
        cell = lambda rec: vr.attention_cell(rec, NOW)
        self.assertEqual(cell(attention("needs_input", "permission", "2026-10-09T11:01:00Z")), ("permission 4m", vr.NEEDS))
        self.assertEqual(cell(attention("needs_input", None, None)), ("needs you", vr.NEEDS))
        self.assertEqual(cell(attention("waiting", "owner arms #15", "2026-10-09T08:05:00Z")),
                         ("waiting 3h: owner arms #15", vr.WAITING))
        self.assertEqual(cell(attention("waiting")), ("waiting", vr.WAITING))
        self.assertEqual(cell(attention("none")), (vr.NONE, vr.DIM))

    def test_what_is_not_known_never_reads_as_nothing_waiting(self):
        self.assertEqual(vr.attention_cell(None, NOW), (vr.UNREAD, vr.DIM))
        self.assertEqual(vr.attention_cell(bad("derived:states+jobs", "states: not known"), NOW), (vr.NOT_READ, vr.FAILED))
        self.assertEqual(vr.attention_cell(attention("later"), NOW), ("unknown", vr.FAILED))
        stale = dict(attention("needs_input", "question"), status="stale", why="states: timed out")
        self.assertEqual(vr.attention_cell(stale, NOW), ("question", vr.WARN))

    def test_every_style_of_the_cell_is_paired_with_a_word(self):
        for rec in (attention("needs_input"), attention("waiting"), attention("none")):
            text, style = vr.attention_cell(rec, NOW)
            self.assertTrue(text.strip(), style)

    def test_the_needs_you_order_puts_the_person_first_the_longest_waiting_first(self):
        agents = [agent("clear", attention("none")),
                  agent("unread", None),
                  agent("waits", attention("waiting", "x", "2026-10-09T09:00:00Z")),
                  agent("asks-late", attention("needs_input", "question", "2026-10-09T11:00:00Z")),
                  agent("asks-unknown", attention("needs_input")),
                  agent("asks-early", attention("needs_input", "permission", "2026-10-09T10:00:00Z"))]
        self.assertEqual([a.login for a in vr.board_order(agents, True, NOW)],
                         ["asks-early", "asks-late", "asks-unknown", "unread", "clear", "waits"],
                         "a job waiting on someone else is not the owner's: it ranks with the rest")
        self.assertEqual(vr.board_order(agents, False, NOW), agents)

    def test_n_and_N_go_round_the_agents_that_need_the_person(self):
        agents = [agent("a", attention("needs_input")), agent("b", attention("waiting")),
                  agent("c", attention("needs_input")), agent("d", None)]
        self.assertEqual(vr.next_needing(agents, 0, 1), 2)
        self.assertEqual(vr.next_needing(agents, 2, 1), 0)
        self.assertEqual(vr.next_needing(agents, 0, -1), 2)
        self.assertIsNone(vr.next_needing(agents[1:2] + agents[3:], 0, 1), "waiting is not on the person")

    def test_the_title_counts_who_needs_you_and_what_is_not_known(self):
        agents = [agent("a", attention("needs_input")), agent("b", None), agent("c", attention("none"))]
        self.assertEqual(vr.board_title(agents, NOW), "Fleet · 1 of 3 need you, 1 not known")
        self.assertEqual(vr.board_title(agents[2:], NOW), "Fleet · 0 of 1 need you")

    def test_compact_keeps_who_whether_and_what_and_the_keys_say_what_they_change_to(self):
        self.assertEqual([c.key for c, _ in vr.board_columns(fleet(), 140, compact=True)], ["login", "attention", "job"])
        lines = texts(vr.board_lines(fleet(), {}, status(), 0, 200, 20, needs_first=True, compact=True))
        self.assertIn("s registry order", lines[-2])
        self.assertIn("v full board", lines[-2])
        lines = texts(vr.board_lines(fleet(), {}, status(), 0, 200, 20, notice="no agent needs you now"))
        self.assertEqual(lines[-3], "no agent needs you now")
        self.assertIn("s needs-you order", lines[-2])

    def test_every_key_is_shown_on_an_80_column_pane(self):
        for needs_first in (True, False):
            for compact in (True, False):
                self.assertLessEqual(vr.cells(vr.board_keys(needs_first, compact)), 80)
        self.assertLessEqual(vr.cells(vr.BOARD_KEYS), 80)
        self.assertTrue(texts(vr.board_lines(fleet(), {}, status(), 0, 80, 20))[-1].endswith("q close"))

    def test_the_full_board_never_cuts_the_age_off_a_reason(self):
        cols = vr.board_columns(fleet(), 140)
        for rec in (attention("needs_input", "permission", "2026-10-08T12:00:00Z"),
                    dict(attention("needs_input", "permission", "2026-10-08T12:00:00Z"), status="stale", why="x")):
            row = texts([vr.board_row(agent("a", rec), cols, False, NOW)])[0]
            self.assertIn("permission 23h", row)

    def test_a_failed_attention_is_named_in_the_footer_with_its_why(self):
        agents = fleet()
        for a in agents:
            a.sections["attention"] = bad("derived:states+jobs", "states: the account's session state is not known")
        lines = texts(vr.failure_lines(agents, vr.BOARD_SECTIONS, 200, limit=3))
        self.assertIn("? attention not read for all agents: states: the account's session state is not known", lines)

    def test_the_agent_view_says_unknown_for_every_field_fleet_could_not_tell(self):
        a = vr.Agent("x", "develop-qzapp", "agent", dict(FULL, attention=attention("needs_input")))
        body = texts(vr.agent_body(a, vr.Samples(), NOW, 100))
        self.assertIn("  needs you: the reason not said, since unknown", body)
        self.assertIn("  context unknown: no sample from the status line", body)
        self.assertIn("  output unknown", body)
        self.assertTrue(any(t.startswith("Attention  derived:states+jobs, 4 min ago") for t in body), "the panel says its age")

    def test_the_agent_view_says_what_fleet_told(self):
        rec = attention("needs_input", "permission", "2026-10-09T11:01:00Z", blocked=1, pending=2,
                        context_pct=63, context_at="2026-10-09T11:02:00Z", output="quiet")
        body = texts(vr.agent_body(vr.Agent("x", "h", "agent", dict(FULL, attention=rec)), vr.Samples(), NOW, 100))
        for line in ("  needs you: a permission prompt, since 11:01Z (4 min ago)", "  jobs blocked 1 · queued 2",
                     "  context 63% in use, sampled 3 min ago",
                     "  output quiet: nothing written in 30 s, which is not idle"):
            self.assertIn(line, body)
        self.assertIn("  nothing waits on you", texts(vr.attention_body(attention("none"), NOW, 100)))
        self.assertIn("  waiting on something not a person, since unknown", texts(vr.attention_body(attention("waiting"), NOW, 100)))


def watched(login, state="idle", level="none", running=False, missing="2026-10-09T11:02:00Z"):
    """An agent as the views see it: states, attention, and the derived watch record."""
    return vr.Agent(login, "develop-qzapp", "agent", {
        "states": ok("op:states", "2026-10-09T11:00:22Z", {"state": state, "sessions": [{"session": "s", "state": state}]}),
        "attention": attention(level),
        "watch": ok("derived:proc", "2026-10-09T11:04:50Z",
                    {"running": running, "missing_since": missing if running is False else None}),
    })


class InboxWatch(unittest.TestCase):
    def test_an_idle_agent_without_a_watch_for_two_minutes_is_flagged_with_how_long(self):
        self.assertEqual(vr.needs_you_cell(watched("a"), NOW), ("inbox off 3m", vr.WAITING))
        long = watched("a", missing="2026-10-08T12:00:00Z")
        row = texts([vr.board_row(long, vr.board_columns([long], 140), False, NOW)])[0]
        self.assertIn("inbox off 23h", row, "the age is never the cut")

    def test_a_short_gap_an_unknown_watch_or_a_busy_session_is_not_flagged(self):
        self.assertEqual(vr.needs_you_cell(watched("a", missing="2026-10-09T11:04:00Z"), NOW), (vr.NONE, vr.DIM))
        self.assertEqual(vr.needs_you_cell(watched("a", running=None), NOW), (vr.NONE, vr.DIM),
                         "a watch fleet.py does not report is unknown, never missing")
        self.assertEqual(vr.needs_you_cell(watched("a", running=True), NOW), (vr.NONE, vr.DIM))
        stale = watched("a", running=None)
        stale.sections["watch"]["data"]["missing_since"] = "2026-10-09T11:00:00Z"
        self.assertIsNone(vr.unwatched_since(stale, NOW), "an earlier missing read does not flag an unknown watch")
        self.assertIsNone(vr.unwatched_since(watched("a", state="working"), NOW))

    def test_a_stale_idle_is_not_idle(self):
        a = watched("a")
        a.sections["states"] = dict(a.sections["states"], status="stale", why="op:states: timed out")
        self.assertIsNone(vr.unwatched_since(a, NOW))

    def test_what_asks_for_the_person_wins_over_the_flag(self):
        text, style = vr.needs_you_cell(watched("a", level="needs_input"), NOW)
        self.assertEqual((text, style), (vr.NEEDS_YOU, vr.NEEDS))

    def test_the_flag_ranks_after_waiting_and_before_what_is_not_known(self):
        agents = [agent("clear", attention("none")), agent("unknown", None), watched("unwatched"),
                  agent("waits", attention("waiting", "x", "2026-10-09T09:00:00Z"))]
        self.assertEqual([a.login for a in vr.board_order(agents, True, NOW)],
                         ["unwatched", "unknown", "clear", "waits"])

    def test_the_title_counts_the_flagged(self):
        self.assertEqual(vr.board_title([watched("a"), watched("b", running=True)], NOW),
                         "Fleet · 0 of 2 need you, 1 no inbox watch")

    def test_the_agent_view_says_running_missing_since_or_unknown(self):
        lines = lambda a: texts(vr.agent_body(a, vr.Samples(), NOW, 100))
        self.assertIn("  inbox watch running", lines(watched("a", running=True)))
        self.assertIn("  inbox watch not running, missing since 11:02Z (3 min ago)", lines(watched("a")))
        self.assertIn("  inbox watch unknown", lines(watched("a", running=None)))


def blocked(login, *jobs, level="waiting"):
    """An agent with these blocked jobs: (id, blocked_on, updated[, cleared])."""
    listed = []
    for job in jobs:
        j = {"id": job[0], "state": "blocked", "title": "t", "blocked_on": job[1], "updated": job[2]}
        if len(job) > 3:
            j["cleared"] = job[3]
        listed.append(j)
    return vr.Agent(login, "develop-qzapp", "agent", {
        "states": ok("op:states", "2026-10-09T11:00:22Z", {"state": "working", "sessions": []}),
        "attention": attention(level),
        "jobs": ok("op:jobs", "2026-10-09T11:00:25Z", {"jobs": {"status": "ok", "jobs": listed}})})


class WaitingOn(unittest.TestCase):
    def test_a_blocker_naming_the_owner_needs_you_and_is_counted(self):
        a = blocked("a", ("j1", "the owner arms #15", "2026-10-09T08:05:00Z"))
        self.assertEqual(vr.needs_you_cell(a, NOW), ("3h: the owner arms #15", vr.NEEDS))
        self.assertEqual(vr.waiting_cell(a, NOW), (vr.NONE, vr.DIM), "said once, where it belongs")
        self.assertEqual(vr.board_title([a], NOW), "Fleet · 1 of 1 need you")
        self.assertEqual(vr.next_needing([a, blocked("b")], 1, 1), 0)

    def test_a_blocker_on_another_agent_waits_and_does_not_need_you(self):
        a = blocked("a", ("j1", "python-dev-01's #204", "2026-10-08T17:00:00Z"))
        self.assertEqual(vr.needs_you_cell(a, NOW), (vr.NONE, vr.DIM))
        self.assertEqual(vr.waiting_cell(a, NOW), ("18h: python-dev-01's #204", vr.WAITING))
        self.assertEqual(vr.board_title([a], NOW), "Fleet · 0 of 1 need you")
        self.assertIsNone(vr.next_needing([a], 0, 1))

    def test_a_cleared_blocker_reads_as_the_agents_to_move_on(self):
        a = blocked("a", ("j1", "pr:org/repo#12", "2026-10-08T17:00:00Z", True))
        self.assertEqual(vr.waiting_cell(a, NOW), ("cleared: pr:org/repo#12", vr.NORMAL))
        owner_cleared = blocked("b", ("j2", "the owner arms #15", "2026-10-09T08:05:00Z", True))
        self.assertEqual(vr.needs_you_cell(owner_cleared, NOW), (vr.NONE, vr.DIM), "a cleared wait is not the owner's")
        self.assertEqual(vr.waiting_cell(owner_cleared, NOW), ("cleared: the owner arms #15", vr.NORMAL))
        not_yet = blocked("c", ("j3", "pr:org/repo#12", "2026-10-08T17:00:00Z", False))
        self.assertEqual(vr.waiting_cell(not_yet, NOW)[1], vr.WAITING)

    def test_the_longest_blocked_job_is_shown_and_owners_words_need_a_whole_word(self):
        a = blocked("a", ("j2", "late", "2026-10-09T10:00:00Z"), ("j1", "early", "2026-10-09T06:00:00Z"),
                    ("j3", "no time", None))
        self.assertEqual(vr.waiting_cell(a, NOW)[0], "5h: early")
        for words in ("co-owner sign-off", "owners of the repo"):
            self.assertIsNone(vr.owner_job(blocked("b", ("j1", words, "2026-10-09T06:00:00Z"))), words)

    def test_unread_or_failed_jobs_say_so_in_the_column(self):
        a = blocked("a")
        a.sections["jobs"] = None
        self.assertEqual(vr.waiting_cell(a, NOW), (vr.UNREAD, vr.DIM))
        a.sections["jobs"] = bad("op:jobs", NOT_OPERATOR)
        self.assertEqual(vr.waiting_cell(a, NOW), (vr.NOT_READ, vr.FAILED))


class Values(unittest.TestCase):
    def test_clock_and_age(self):
        self.assertEqual(vr.clock("2026-10-09T10:57:46Z", NOW), "10:57Z")
        self.assertEqual(vr.clock("2026-10-08T10:57:46Z", NOW), "Oct 08")
        self.assertEqual(vr.clock(None, NOW), vr.NONE)
        self.assertEqual(vr.age("2026-10-09T11:04:30Z", NOW), "30 s ago")
        self.assertEqual(vr.age("2026-10-07T11:04:30Z", NOW), "2 d ago")
        self.assertEqual(vr.age(None, NOW), "never")
        self.assertEqual([vr.short_age(t, NOW) for t in ("2026-10-09T11:04:15Z", "2026-10-09T10:05:00Z", "2026-10-07T11:00:00Z", None)],
                         ["45s", "1h", "2d", ""])

    def test_sizes_and_counts(self):
        self.assertEqual(vr.size_kb(531684), "519M")
        self.assertEqual(vr.size_kb(3 * 1024 * 1024), "3.0G")
        self.assertEqual(vr.count(43_650_000), "43.6M")
        self.assertEqual(vr.count(999), "999")


if __name__ == "__main__":
    unittest.main()
