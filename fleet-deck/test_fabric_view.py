"""fabric_view: input, the refresh rule, and where its data comes from."""

import json
import os
import re
import tempfile
import unittest

import fabric_view as fv
from deck_tabs import PANE_ROLES
from fabric_deck import agent_view_command, view_title


class Input(unittest.TestCase):
    def test_focus_reports_and_keys(self):
        events, rest = fv.parse_input(b"\x1b[Ojr\x1b[I\x1b[A\r", final=False)
        self.assertEqual(events, [fv.FOCUS_OUT, "j", "r", fv.FOCUS_IN, fv.UP, fv.ENTER])
        self.assertEqual(rest, b"")

    def test_a_sequence_split_across_reads_is_kept_for_the_next(self):
        events, rest = fv.parse_input(b"j\x1b[", final=False)
        self.assertEqual((events, rest), (["j"], b"\x1b["))
        events, rest = fv.parse_input(rest + b"O", final=False)
        self.assertEqual((events, rest), ([fv.FOCUS_OUT], b""))

    def test_a_lone_escape_is_the_escape_key_once_nothing_follows(self):
        self.assertEqual(fv.parse_input(b"\x1b", final=False), ([], b"\x1b"))
        self.assertEqual(fv.parse_input(b"\x1b", final=True), ([fv.ESCAPE], b""))

    def test_an_unknown_sequence_never_acts_as_its_letters(self):
        events, _ = fv.parse_input(b"\x1b[200~q\x1b[1;5Cr", final=False)
        self.assertEqual(events, ["q", "r"])   # the q and r typed between, not the sequences' own letters

    def test_ctrl_c_closes(self):
        self.assertEqual(fv.parse_input(b"\x03", final=False)[0], ["q"])


class Refresh(unittest.TestCase):
    def test_once_at_open_whatever_the_focus_then_nothing_without_it(self):
        for focus in (None, False, True):
            r = fv.Refresher({"proc": 5, "jobs": 30})
            self.assertEqual(r.due(0, focused=focus), ["proc", "jobs"])
            for s in ("proc", "jobs"):
                r.started(s)
                r.ended(s, 1)
            self.assertEqual(r.due(100, focused=focus), ["proc", "jobs"] if focus else [])

    def test_each_section_again_after_its_ttl_and_never_twice_at_once(self):
        r = fv.Refresher({"proc": 5, "jobs": 30})
        for s in r.due(0, True):
            r.started(s)
        self.assertEqual(r.due(100, True), [])        # still running
        r.ended("proc", 10)
        r.ended("jobs", 10)
        self.assertEqual(r.due(14, True), [])
        self.assertEqual(r.due(15, True), ["proc"])
        self.assertEqual(r.due(40, True), ["proc", "jobs"])
        self.assertEqual(r.due(40, False), [])
        self.assertEqual(r.due(40, None), [])

    def test_the_agent_pane_fetches_nothing_until_its_first_focus(self):
        # Every account tab's agent pane starts with the deck: none of them
        # reads the fleet until a person looks.
        r = fv.Refresher({"proc": 5, "jobs": 30}, lazy=True)
        self.assertEqual(r.due(0, None), [])
        self.assertEqual(r.due(0, False), [])
        self.assertEqual(r.due(0, True), ["proc", "jobs"])
        for s in ("proc", "jobs"):
            r.started(s)
            r.ended(s, 1)
        self.assertEqual(r.due(100, False), [], "and, as any view, nothing while unfocused")
        self.assertEqual(r.due(100, True), ["proc", "jobs"])

    def test_r_refetches_what_is_not_already_running(self):
        r = fv.Refresher({"proc": 5, "jobs": 30})
        r.started("jobs")
        self.assertEqual(r.refetch(), ["proc"])


# An account tab as `pane list` gives it, and another tab beside it.
TAB_PANES = [
    {"pane_id": "h", "tab_id": "t1", "label": "harness"},
    {"pane_id": "s", "tab_id": "t1", "label": "shell"},
    {"pane_id": "st", "tab_id": "t1", "label": "status"},
    # A running view's title: it hears focus changes (fabric_deck.view_ready).
    {"pane_id": "a", "tab_id": "t1", "label": "agent", "terminal_title": "fabric-view agent ui"},
    {"pane_id": "a2", "tab_id": "t2", "label": "agent"},
]


def acts(herdr):
    """What a toggle did to the tab, without its looks at it."""
    return [c for c in herdr.calls if c[:2] in (("pane", "zoom"), ("pane", "run"), ("plugin", "pane"))]


def mark_of(herdr):
    """The start mark a toggle typed with the view it restarted."""
    run = next(c[3] for c in herdr.calls if c[:2] == ("pane", "run"))
    return re.search(r"FABRIC_VIEW_START=(\w+) ", run).group(1)
BARE = {"shell_pid": 10, "foreground_process_group_id": 10,
        "foreground_processes": [{"pid": 10, "argv": ["bash"]}]}
# ui's view, as fabric-view's launcher leaves it in the pane.
VIEWING = {"shell_pid": 10, "foreground_process_group_id": 40, "foreground_processes": [{"pid": 40, "argv": [
    "fabric-python", "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1]); from fabric_view import main",
    "/x/fleet-deck", "agent", "--agent", "ui", "--in-tab"]}]}
# Something else the operator runs in the agent pane.
EDITING = {"shell_pid": 10, "foreground_process_group_id": 50,
           "foreground_processes": [{"pid": 50, "argv": ["vim", "notes"]}]}


class FakeHerdr:
    def __init__(self, panes, proc):
        self.panes, self.proc, self.calls = panes, proc, []

    def call(self, *args):
        self.calls.append(args)
        return {"panes": self.panes} if args[:2] == ("pane", "list") else {}

    def process_info(self, pane):
        return self.proc[pane]


# The toggle's lock lives here, never beside a running deck's.
LOCK_DIR = tempfile.TemporaryDirectory()
_REAL_VIEW_MARK = fv.view_mark


def setUpModule():
    # A fake view's pid is no process of this host: its mark is never read
    # from the host's /proc. A test that needs one patches it again.
    fv.view_mark = lambda pid: None


def tearDownModule():
    fv.view_mark = _REAL_VIEW_MARK
    LOCK_DIR.cleanup()


def context(tab_id="t1", focused="h", label="ui"):
    return {fv.LOCK_DIR_ENV: LOCK_DIR.name, "HERDR_PLUGIN_CONTEXT_JSON": json.dumps(
        {"tab_id": tab_id, "tab_label": label, "focused_pane_id": focused})}


def fv_polls():
    from fabric_deck import VIEW_START_POLLS
    return VIEW_START_POLLS


class LiveTab(FakeHerdr):
    """A tab that changes under the toggle: an overlay opened is listed from
    then on, one closed is gone."""

    def call(self, *args):
        if args[:3] == ("plugin", "pane", "close"):
            self.panes = [p for p in self.panes if p["pane_id"] != args[3]]
        return super().call(*args)


class Toggle(unittest.TestCase):
    def test_one_chord_turns_the_tab_over_and_back(self):
        roles = fv.tab_roles(TAB_PANES, "t1")
        self.assertEqual(roles, {"harness": "h", "shell": "s", "status": "st", "agent": "a"})
        self.assertEqual(fv.toggle_step(roles, "h"), ("a", "--on"))
        self.assertEqual(fv.toggle_step(roles, "a"), ("h", "--off"), "the same chord, back")
        self.assertEqual(fv.toggle_step(roles, "s"), ("a", "--on"), "from anywhere else in the tab")

    def test_a_repeated_label_names_the_pane_the_deck_follows(self):
        from fabric_deck import PaneInfo, read_tab
        panes = [{"pane_id": "h", "tab_id": "t1", "label": "harness"},
                 {"pane_id": "a1", "tab_id": "t1", "label": "agent"},
                 {"pane_id": "a2", "tab_id": "t1", "label": "agent"}]
        deck = read_tab("ui", "t1", "w", [PaneInfo(p["pane_id"], p["tab_id"], p["label"]) for p in panes])
        self.assertEqual(fv.tab_roles(panes, "t1"), deck.panes)

    def test_a_tab_without_both_panes_is_none_of_the_toggles(self):
        self.assertIsNone(fv.toggle_step(fv.tab_roles(TAB_PANES, "t2"), "a2"))
        self.assertIsNone(fv.toggle_step(fv.tab_roles(TAB_PANES, None), "h"))

    def test_only_the_zoom_changes_while_the_view_runs(self):
        herdr = FakeHerdr(TAB_PANES, {"a": VIEWING})
        self.assertEqual(fv.toggle(context(focused="h"), herdr), 0)
        self.assertEqual(acts(herdr), [("pane", "zoom", "a", "--on")])
        herdr.calls.clear()
        fv.toggle(context(focused="a"), herdr)
        self.assertEqual(acts(herdr), [("pane", "zoom", "h", "--off")], "the harness pane, never typed into")

    def test_a_view_in_the_tab_clears_its_title_as_it_ends(self):
        self.assertEqual(fv.closing(True), fv.FOCUS_OFF + "\x1b]2;\x07")
        self.assertEqual(fv.closing(False), fv.FOCUS_OFF, "an overlay's title is FleetDeck's")

    def test_focus_waits_for_a_view_still_starting(self):
        # The deck started it unfocused a moment ago, marked m7: focus moved
        # there before it reports focus would be dropped, and it would wait
        # for a key. The title a killed view left is not its sign.
        starting = [dict(p, terminal_title="fabric-view agent ui m6") if p["pane_id"] == "a" else p
                    for p in TAB_PANES]
        herdr = FakeHerdr(starting, {"a": VIEWING})
        looks = []

        def sleep(_):
            looks.append(1)
            if len(looks) == 2:
                herdr.panes = [dict(p, terminal_title=view_title("ui", "m7")) if p["pane_id"] == "a" else p
                               for p in herdr.panes]
                self.assertEqual(acts(herdr), [], "nothing zoomed yet")

        real, fv.view_mark = fv.view_mark, lambda pid: "m7" if pid == 40 else None
        try:
            fv.toggle(context(focused="h"), herdr, sleep=sleep)
        finally:
            fv.view_mark = real
        self.assertEqual(len(looks), 2)
        self.assertEqual(acts(herdr), [("pane", "zoom", "a", "--on")])

    def test_a_view_that_never_reports_ready_is_shown_and_said(self):
        import contextlib
        import io
        herdr = FakeHerdr([dict(p, terminal_title="bash") if p["pane_id"] == "a" else p for p in TAB_PANES],
                          {"a": VIEWING})
        looks, said = [], io.StringIO()
        with contextlib.redirect_stderr(said):
            self.assertEqual(fv.toggle(context(focused="h"), herdr, sleep=lambda _: looks.append(1)), 0)
        self.assertEqual(len(looks), fv_polls(), "waited to the bound")
        self.assertEqual(acts(herdr), [("pane", "zoom", "a", "--on")], "and shown anyway")
        self.assertIn("did not report ready", said.getvalue())

    def test_focus_moves_at_once_where_no_view_of_this_login_can_be_waited_for(self):
        for label, held in (("ui", EDITING), ("ui; x", VIEWING), ("ui; x", BARE)):
            herdr = FakeHerdr([dict(p, terminal_title=None) for p in TAB_PANES], {"a": held})
            looks = []
            fv.toggle(context(focused="h", label=label), herdr, sleep=lambda _: looks.append(1))
            self.assertEqual((looks, acts(herdr)), ([], [("pane", "zoom", "a", "--on")]), (label, held))

    def test_a_view_titles_itself_with_its_start(self):
        self.assertEqual(fv.in_tab_title("ui", {"FABRIC_VIEW_START": "m7"}), view_title("ui", "m7"))
        self.assertEqual(fv.in_tab_title("ui", {}), view_title("ui"))
        self.assertIsNone(fv.in_tab_title(None, {"FABRIC_VIEW_START": "m7"}))

    def test_a_view_that_ended_is_started_again_where_it_is_shown(self):
        herdr = FakeHerdr(TAB_PANES, {"a": BARE})
        fv.toggle(context(focused="h"), herdr, sleep=lambda s: None)
        # Zoomed first, so it starts at the size it is seen at; the zoom
        # focuses the pane before the view reports focus: it is told, or it
        # would wait for a key before its first fetch.
        self.assertEqual(acts(herdr), [("pane", "zoom", "a", "--on"),
                                       ("pane", "run", "a", agent_view_command("ui", True, mark_of(herdr)))])
        self.assertTrue(acts(herdr)[1][3].startswith(f"env {fv.OPENED_FOCUSED}=1 FABRIC_VIEW_START="))

    def test_the_press_holds_on_until_the_view_can_hear_the_next_one(self):
        # Let go before the view turns focus reporting on, a second press
        # would move the focus away unheard, and the view would fetch hidden.
        herdr = FakeHerdr(TAB_PANES, {"a": BARE})
        looks = []

        def sleep(_):
            looks.append(1)
            if len(looks) == 3:
                herdr.panes = [dict(p, terminal_title=view_title("ui", mark_of(herdr))) if p["pane_id"] == "a" else p
                               for p in herdr.panes]

        fv.toggle(context(focused="h"), herdr, sleep=sleep)
        self.assertEqual(len(looks), 3, "it waits for this start's title, and no longer")
        looks.clear()
        # TAB_PANES still carries the title an earlier view left: not this one.
        fv.toggle(context(focused="h"), FakeHerdr(TAB_PANES, {"a": BARE}), sleep=lambda _: looks.append(1))
        self.assertEqual(len(looks), fv_polls() + 1, "an earlier view's title is no sign; let go at the bound")

    def test_a_label_that_is_no_plain_login_is_never_typed(self):
        herdr = FakeHerdr(TAB_PANES, {"a": BARE})
        fv.toggle(context(focused="h", label="ui; rm -rf ~"), herdr, sleep=lambda s: None)
        self.assertEqual(acts(herdr), [("pane", "zoom", "a", "--on")])

    def test_a_tab_the_deck_does_not_keep_opens_the_overlay(self):
        opened = []
        real, fv.open_overlay = fv.open_overlay, lambda env: opened.append(env) or 0
        try:
            herdr = FakeHerdr(TAB_PANES[:3], {})
            self.assertEqual(fv.toggle(context(focused="h"), herdr), 0)
        finally:
            fv.open_overlay = real
        self.assertEqual(len(opened), 1)
        self.assertFalse(any(c[1] == "zoom" for c in herdr.calls))

    def test_a_press_left_behind_while_the_view_came_up_does_not_take_the_person_back(self):
        starting = [dict(p, terminal_title="bash") if p["pane_id"] == "a" else p for p in TAB_PANES]
        herdr = FakeHerdr([dict(p, focused=p["pane_id"] == "h") for p in starting], {"a": VIEWING})
        looks = []

        def sleep(_):
            looks.append(1)
            if len(looks) == 2:   # ready, and the person has gone to t2 meanwhile
                herdr.panes = [dict(p, focused=p["pane_id"] == "a2") for p in TAB_PANES]

        fv.toggle(context(focused="h"), herdr, sleep=sleep)
        self.assertEqual(acts(herdr), [], "no zoom pulls them back")

    def test_a_press_from_a_tab_the_person_has_left_does_nothing(self):
        # Pressed in t1, run after the person went to t2: FleetDeck opens an
        # overlay in the tab shown, and zooms whatever it is told.
        opened = []
        for panes in (TAB_PANES[:3], TAB_PANES):
            left = [dict(p, focused=p["pane_id"] == "a2") for p in panes + [TAB_PANES[4]]]
            herdr = FakeHerdr(left, {"a": VIEWING})
            real, fv.open_overlay = fv.open_overlay, lambda env: opened.append(env) or 0
            try:
                self.assertEqual(fv.toggle(context(tab_id="t1", focused="h"), herdr), 0)
            finally:
                fv.open_overlay = real
            self.assertEqual((acts(herdr), opened), ([], []))

    def test_two_presses_at_once_open_one_overlay_and_close_it(self):
        import threading
        import time as clock
        herdr = LiveTab(list(TAB_PANES[:3]), {})
        opened = []

        def open_overlay(env):
            clock.sleep(0.05)   # FleetDeck making the pane, while the other press waits
            opened.append(env)
            herdr.panes = [*herdr.panes, {"pane_id": f"o{len(opened)}", "tab_id": "t1", "label": fv.OVERLAY_TITLE}]
            return 0

        real, fv.open_overlay = fv.open_overlay, open_overlay
        try:
            presses = [threading.Thread(target=fv.toggle, args=(context(focused="h"), herdr)) for _ in range(2)]
            for press in presses:
                press.start()
            for press in presses:
                press.join()
        finally:
            fv.open_overlay = real
        self.assertEqual(len(opened), 1, "the second press found the first one's overlay")
        self.assertFalse(any(p["label"] == fv.OVERLAY_TITLE for p in herdr.panes), "and closed it")

    def test_the_overlay_is_opened_and_waited_for_within_a_bound(self):
        import subprocess
        runs = []
        real = subprocess.run
        subprocess.run = lambda argv, **kw: runs.append((argv, kw)) or subprocess.CompletedProcess(argv, 0)
        try:
            self.assertEqual(fv.open_overlay({"HERDR_BIN_PATH": "/x/fd"}), 0)
        finally:
            subprocess.run = real
        self.assertEqual(runs[0][0], fv.open_argv("/x/fd", fv.PLUGIN_ID, "agent"))
        self.assertEqual(runs[0][1].get("timeout"), fv.OPEN_TIMEOUT_S)

    def test_a_press_that_finds_the_overlay_open_closes_it_whatever_it_was_told(self):
        # Two presses read at once both carry the harness as focused; the
        # second runs after the first opened the overlay, and closes it.
        overlay = {"pane_id": "o", "tab_id": "t1", "label": fv.OVERLAY_TITLE}
        herdr = FakeHerdr([*TAB_PANES[:3], overlay], {})
        self.assertEqual(fv.toggle(context(focused="h"), herdr), 0)
        self.assertEqual(herdr.calls[1:], [("plugin", "pane", "close", "o")])

    def test_the_focus_is_the_tabs_as_it_is_not_as_the_key_found_it(self):
        # A press read while the previous one was still zooming: its context
        # says the harness, the tab already shows the agent pane.
        panes = [dict(p, focused=p["pane_id"] == "a") for p in TAB_PANES]
        herdr = FakeHerdr(panes, {"a": VIEWING})
        fv.toggle(context(focused="h"), herdr)
        self.assertEqual(herdr.calls[1:], [("pane", "zoom", "h", "--off")])


    def test_the_same_chord_closes_the_overlay_it_opened(self):
        overlay = {"pane_id": "o", "tab_id": "t1", "label": fv.OVERLAY_TITLE}
        herdr = FakeHerdr([*TAB_PANES[:3], overlay], {})
        self.assertEqual(fv.toggle(context(focused="o"), herdr), 0)
        self.assertEqual(herdr.calls[1:], [("plugin", "pane", "close", "o")])

    def test_the_overlay_is_never_taken_for_the_decks_agent_pane(self):
        # FleetDeck labels a plugin pane with its title.
        import tomllib
        with open(os.path.join(os.path.dirname(os.path.abspath(fv.__file__)), "herdr-plugin.toml"), "rb") as f:
            panes = {p["id"]: p for p in tomllib.load(f)["panes"]}
        self.assertEqual(panes["agent"]["title"], fv.OVERLAY_TITLE)
        self.assertNotIn(fv.OVERLAY_TITLE, PANE_ROLES)

    def test_in_tab_needs_its_login_and_toggle_takes_nothing(self):
        import contextlib, io
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fv.main(["agent", "--in-tab"]), 2)
            self.assertEqual(fv.main(["agent", "--in-tab", "--agent", "ui"]), 2)
            self.assertEqual(fv.main(["toggle", "ui"]), 2)


class Sources(unittest.TestCase):
    def test_root_from_the_environment_else_the_installed_fabric_ctl(self):
        self.assertEqual(fv.fabric_root({"AGENT_FABRIC_ROOT": "/af"}, lambda _: None), "/af")
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "af", "bin"))
            os.makedirs(os.path.join(d, "path"))
            real = os.path.join(d, "af", "bin", "fabric-ctl")
            open(real, "w").close()
            link = os.path.join(d, "path", "fabric-ctl")
            os.symlink(real, link)
            self.assertEqual(fv.fabric_root({"AGENT_FABRIC_ROOT": ""}, lambda _: link), os.path.realpath(os.path.join(d, "af")))
        self.assertIsNone(fv.fabric_root({}, lambda _: None))

    def test_the_overlays_login_is_its_tabs_label(self):
        ctx = {"tab_id": "w1:t3", "tab_label": "web-dev-02", "focused_pane_id": "w1:p9"}
        self.assertEqual(fv.context_login({"HERDR_PLUGIN_CONTEXT_JSON": json.dumps(ctx)}), "web-dev-02")
        self.assertIsNone(fv.context_login({"HERDR_PLUGIN_CONTEXT_JSON": json.dumps({"tab_id": "w1:t3"})}))
        self.assertIsNone(fv.context_login({"HERDR_PLUGIN_CONTEXT_JSON": "not json"}))
        self.assertIsNone(fv.context_login({}))

    def test_one_host_record_per_machine_the_freshest_answer(self):
        import view_render as vr
        old = {"status": "ok", "src": "op:host", "at": "2026-10-09T11:00:00Z", "data": {"machine": {}}}
        new = dict(old, at="2026-10-09T11:01:00Z")
        down = {"status": "failed", "src": "op:host", "at": "2026-10-09T11:02:00Z", "why": "x"}
        agents = [vr.Agent("a", "h1", "agent", {"host": down}), vr.Agent("b", "h1", "agent", {"host": old}),
                  vr.Agent("c", "h1", "agent", {"host": new}), vr.Agent("d", "h2", "agent", {"host": None})]
        self.assertEqual(fv.host_records(agents), {"h1": new, "h2": None})


class Records(unittest.TestCase):
    def test_a_failed_fetch_of_the_whole_section_wins_over_an_older_record(self):
        from types import SimpleNamespace
        store = fv.Store()
        old = {"status": "ok", "src": "op:jobs", "at": "2026-10-09T10:00:00Z", "data": {"jobs": {"jobs": []}}}
        store.put("jobs", {"alice": old})
        placements = {"alice": SimpleNamespace(host="h", kind="agent")}
        shown = fv.agents_of(placements, store, ("jobs",), {"jobs": "FleetError: alice is not a placed account"})
        self.assertEqual(shown[0].sections["jobs"]["status"], "failed")
        self.assertIn("not a placed account", shown[0].sections["jobs"]["why"])
        self.assertIs(fv.agents_of(placements, store, ("jobs",), {})[0].sections["jobs"], old)


def agent(login, level):
    data = {"level": level, "reason": None, "since": None}
    rec = {"status": "ok", "src": "derived:states+jobs", "at": "2026-10-09T11:00:00Z", "data": data} if level else None
    return fv.vr.Agent(login, "h", "agent", {"attention": rec})


class Attention(unittest.TestCase):
    """attention is told from states and jobs with fleet.py's own reader."""

    def fleet(self, reader=None):
        from types import SimpleNamespace
        sections = {"states": SimpleNamespace(ttl=30, derives=()), "jobs": SimpleNamespace(ttl=30, derives=()),
                    "attention": SimpleNamespace(ttl=0, derives=("states", "jobs"))}
        return SimpleNamespace(SECTIONS=sections, attention_record=reader)

    def test_it_is_never_fetched_on_its_own(self):
        import queue
        view = fv.View(self.fleet(), ("states", "attention", "jobs"), None, fv.Store(), queue.Queue())
        self.assertEqual(sorted(view.refresher.due(0, True)), ["jobs", "states"])
        self.assertNotIn("attention", view.whys)

    def test_unread_inputs_are_unknown_and_a_reader_that_fails_is_a_failure(self):
        from types import SimpleNamespace
        placements = {"alice": SimpleNamespace(host="h", kind="agent")}
        store = fv.Store()
        seen = []
        fleet = self.fleet(lambda st, jo, now: seen.append((st, jo)) or {"status": "ok", "data": {"level": "none"}})
        self.assertIsNone(fv.agents_of(placements, store, ("states", "jobs", "attention"), {}, fleet)[0].sections["attention"])
        store.put("states", {"alice": {"status": "ok", "at": "t", "data": {}}})
        store.put("jobs", {"alice": {"status": "ok", "at": "t", "data": {}}})
        shown = fv.agents_of(placements, store, ("states", "jobs", "attention"), {}, fleet)[0]
        self.assertEqual(shown.sections["attention"]["data"], {"level": "none"})
        self.assertEqual(seen[0], (store.get("states", "alice"), store.get("jobs", "alice")))

        def broken(*_):
            raise KeyError("data")
        shown = fv.agents_of(placements, store, ("states", "jobs", "attention"), {}, self.fleet(broken))[0]
        self.assertEqual(shown.sections["attention"]["status"], "failed")

    def test_a_fleet_py_without_attention_is_said(self):
        import queue
        from types import SimpleNamespace
        fleet = SimpleNamespace(SECTIONS={"states": SimpleNamespace(ttl=30)})
        view = fv.View(fleet, ("states", "attention"), None, fv.Store(), queue.Queue())
        self.assertIn("serves no attention section", view.whys["attention"])


AGENT_FABRIC = os.environ.get("AGENT_FABRIC_ROOT") or os.path.join(os.path.dirname(__file__), "..", "..", "agent-fabric")


@unittest.skipUnless(os.path.isfile(os.path.join(AGENT_FABRIC, "tools", "fabric", "fleet.py")),
                     "no agent-fabric checkout beside this one (set AGENT_FABRIC_ROOT)")
class AttentionWithFleetPy(unittest.TestCase):
    """The real fleet.py: what the board draws is what fabric-fleet --json says."""

    def test_a_blocked_session_reads_as_its_reason_on_the_board(self):
        from types import SimpleNamespace
        fleet = fv.import_fleet(AGENT_FABRIC)
        if not hasattr(fleet, "attention_record"):
            self.skipTest("this agent-fabric checkout predates the attention section")
        at = "2026-10-09T11:00:22Z"
        store = fv.Store()
        store.put("states", {"alice": {"status": "ok", "src": "op:states", "at": at, "data": {
            "state": "blocked", "reason": "permission", "since": "2026-10-09T11:00:00Z",
            "sessions": [{"session": "s", "state": "blocked"}]}}})
        store.put("jobs", {"alice": {"status": "ok", "src": "op:jobs", "at": at, "data": {"jobs": {"status": "ok", "jobs": [
            {"id": "j1", "state": "queued", "updated": at}]}}}})
        a = fv.agents_of({"alice": SimpleNamespace(host="h", kind="agent")}, store, ("states", "jobs", "attention"), {}, fleet)[0]
        self.assertEqual(a.sections["attention"]["data"]["level"], "needs_input")
        self.assertIsNone(a.sections["attention"]["data"]["context_pct"], "not sampled is unknown, never 0")
        now = fv.vr.parse_utc("2026-10-09T11:05:00Z")
        self.assertEqual(fv.vr.attention_cell(a.sections["attention"], now), ("permission 5m", fv.vr.NEEDS))
        store.put("states", {"alice": {"status": "ok", "src": "op:states", "at": at, "data": {"state": "unknown"}}})
        a = fv.agents_of({"alice": SimpleNamespace(host="h", kind="agent")}, store, ("states", "jobs", "attention"), {}, fleet)[0]
        self.assertEqual(fv.vr.attention_cell(a.sections["attention"], now), (fv.vr.NOT_READ, fv.vr.FAILED))


class InboxWatch(unittest.TestCase):
    def proc(self, at, watch="absent"):
        data = {"rss_kb": 1}
        if watch != "absent":
            data["inbox_watch"] = watch
        return {"status": "ok", "src": "proc-local", "at": at, "data": data}

    def test_the_store_keeps_when_the_watch_was_first_read_missing_until_it_runs(self):
        store = fv.Store()
        store.put("proc", {"a": self.proc("2026-10-09T11:00:00Z", False)})
        store.put("proc", {"a": self.proc("2026-10-09T11:01:00Z", False)})
        self.assertEqual(store.watch_missing["a"], "2026-10-09T11:00:00Z")
        store.put("proc", {"a": self.proc("2026-10-09T11:02:00Z", None)})
        self.assertEqual(store.watch_missing["a"], "2026-10-09T11:00:00Z", "an unread watch does not reset it")
        store.put("proc", {"a": self.proc("2026-10-09T11:03:00Z", True)})
        self.assertNotIn("a", store.watch_missing)

    def test_the_cache_put_at_open_times_nothing_the_first_fetched_read_does(self):
        store = fv.Store()
        store.put("proc", {"a": self.proc("2026-10-09T12:00:00Z", False)}, fetched=False)
        self.assertNotIn("a", store.watch_missing, "a cache may be days old")
        store.put("proc", {"a": self.proc("2026-10-11T11:59:55Z", False)})
        self.assertEqual(store.watch_missing["a"], "2026-10-11T11:59:55Z")

    def test_a_read_time_that_is_not_one_is_not_kept(self):
        store = fv.Store()
        store.put("proc", {"a": self.proc("yesterday", False)})
        self.assertNotIn("a", store.watch_missing)

    def test_agents_of_draws_the_watch_from_proc_and_the_missing_time(self):
        from types import SimpleNamespace
        store = fv.Store()
        store.put("proc", {"a": self.proc("2026-10-09T11:00:00Z", False)})
        placements = {"a": SimpleNamespace(host="h", kind="agent")}
        shown = fv.agents_of(placements, store, ("states", "proc"), {})[0]
        self.assertEqual(shown.sections["watch"]["data"],
                         {"running": False, "missing_since": "2026-10-09T11:00:00Z"})
        self.assertNotIn("watch", fv.agents_of(placements, store, ("states",), {})[0].sections)

    def test_a_fleet_py_without_inbox_watch_reads_unknown(self):
        self.assertIsNone(fv.inbox_watch(self.proc("t")))
        self.assertIsNone(fv.inbox_watch({"status": "failed", "why": "x"}))
        self.assertIsNone(fv.watch_of(None, None))
        rec = fv.watch_of(self.proc("t", False), "2026-10-09T11:00:00Z")
        self.assertEqual(rec["data"], {"running": False, "missing_since": "2026-10-09T11:00:00Z"})
        self.assertEqual(fv.watch_of(self.proc("t"), "x")["data"], {"running": None, "missing_since": None})


class Navigation(unittest.TestCase):
    def test_the_fleet_tabs_screens_are_a_key_away_and_esc_leaves_prs_for_where_it_was(self):
        nav = fv.Nav(fv.BOARD)
        self.assertIsNone(nav.key("c", rows=3, page=10))
        self.assertEqual(nav.screen, fv.COMPARE)
        nav.key("P", 3, 10)
        self.assertEqual((nav.screen, nav.back), (fv.PRS, fv.COMPARE))
        nav.key(fv.ESCAPE, 3, 10)
        self.assertEqual((nav.screen, nav.back), (fv.COMPARE, None))
        nav.key("p", 3, 10)
        nav.key("b", 3, 10)
        self.assertEqual(nav.screen, fv.BOARD)
        self.assertEqual(nav.key(fv.ESCAPE, 3, 10), None)   # Esc on the board closes nothing

    def test_the_popup_is_prs_alone_and_esc_closes_it(self):
        nav = fv.Nav(fv.PRS)
        nav.key("c", 3, 10)
        self.assertEqual(nav.screen, fv.PRS)
        self.assertEqual(nav.key(fv.ESCAPE, 3, 10), fv.QUIT)

    def test_metrics_cycle_both_ways_and_by_number(self):
        nav = fv.Nav(fv.COMPARE)
        nav.key(fv.LEFT, 3, 10)
        self.assertEqual(nav.metric, len(fv.rr.METRICS) - 1)
        nav.key(fv.RIGHT, 3, 10)
        self.assertEqual(nav.metric, 0)
        nav.key("5", 3, 10)
        self.assertEqual(nav.metric, 4)
        nav.key("9", 3, 10)
        self.assertEqual(nav.metric, 4)

    def test_enter_opens_the_selected_agent_and_selection_is_clamped(self):
        nav = fv.Nav(fv.BOARD)
        for _ in range(5):
            nav.key(fv.DOWN, rows=3, page=10)
        self.assertEqual(nav.selected, 2)
        self.assertEqual(nav.key(fv.ENTER, 3, 10), fv.OPEN_AGENT)
        self.assertIsNone(fv.Nav(fv.BOARD).key(fv.ENTER, rows=0, page=10))

    def test_the_selection_follows_its_agent_when_the_order_changes(self):
        nav = fv.Nav(fv.BOARD)
        rows = [agent("a", "none"), agent("b", "none"), agent("c", "none")]
        nav.place(rows)
        nav.key(fv.DOWN, 3, 10)
        self.assertEqual(nav.login, "b")
        nav.place([rows[1], rows[0], rows[2]])     # b now needs the person, and leads
        self.assertEqual((nav.selected, nav.login), (0, "b"))
        nav.place([rows[0], rows[2]])               # b left the registry
        self.assertEqual((nav.selected, nav.login), (0, "a"))

    def test_n_and_N_jump_to_who_needs_the_person_and_say_when_nobody_does(self):
        nav = fv.Nav(fv.BOARD)
        nav.place([agent("a", "needs_input"), agent("b", "waiting"), agent("c", "needs_input")])
        nav.key("n", 3, 10)
        self.assertEqual(nav.login, "c")
        nav.key("n", 3, 10)
        self.assertEqual(nav.login, "a")
        nav.key("N", 3, 10)
        self.assertEqual(nav.login, "c")
        nav.place([agent("a", "waiting"), agent("b", None)])
        nav.key("n", 2, 10)
        self.assertEqual((nav.login, nav.notice), ("b", "none known to need you; 1 cannot be told (? on the board)"),
                         "an agent that cannot be told may need you")
        nav.place([agent("a", "waiting")])
        nav.key("n", 1, 10)
        self.assertEqual(nav.notice, "no agent needs you now")
        nav.key(fv.DOWN, 2, 10)
        self.assertIsNone(nav.notice, "the notice lasts until the next key")

    def test_s_and_v_switch_the_order_and_the_density(self):
        nav = fv.Nav(fv.BOARD)
        self.assertEqual((nav.needs_first, nav.compact), (True, False))
        nav.key("s", 3, 10)
        nav.key("v", 3, 10)
        self.assertEqual((nav.needs_first, nav.compact), (False, True))

    def test_arrows_are_parsed(self):
        self.assertEqual(fv.parse_input(b"\x1b[C\x1b[D\x1bOC", final=False)[0], [fv.RIGHT, fv.LEFT, fv.RIGHT])

    def test_a_popup_is_opened_sized_and_focused(self):
        argv = fv.open_argv("/bin/herdr", "fabric.fleet", "prs")
        self.assertEqual(argv[argv.index("--width") + 1], "80%")
        self.assertIn("--focus", argv)
        self.assertNotIn("--width", fv.open_argv("/bin/herdr", "fabric.fleet", "board"))


class FleetWide(unittest.TestCase):
    def test_plans_come_from_the_documents_top_level(self):
        rec = {"status": "ok", "src": "fabric-plan", "at": "t", "data": {"login": "user", "plans": []}}
        self.assertEqual(fv.answer_of({"agents": [], "plans": rec}, "plans"), ({fv.FLEET: rec}, None, {}))
        records, why, _ = fv.answer_of({"agents": []}, "plans")
        self.assertEqual(records, {})
        self.assertIn("no plans", why)

    def test_prs_carry_the_unplaced_record_beside_them(self):
        rec = {"status": "ok", "src": "pr-gate", "at": "t", "data": {"prs": []}}
        unplaced = {"status": "ok", "src": "pr-gate", "at": "t", "data": {"prs": [{"pr": 1}]}}
        doc = {"agents": [{"login": "a", "sections": {"prs": rec}}], "prs_unplaced": unplaced}
        self.assertEqual(fv.answer_of(doc, "prs"), ({"a": rec}, None, {fv.UNPLACED: {fv.FLEET: unplaced}}))

    def test_a_fleet_py_without_prs_unplaced_is_said_not_shown_as_none(self):
        import report_render as rr
        import view_render as vr
        rec = {"status": "ok", "src": "pr-gate", "at": "t", "data": {"prs": []}}
        _, _, extra = fv.answer_of({"agents": [{"login": "a", "sections": {"prs": rec}}]}, "prs")
        unplaced = extra[fv.UNPLACED][fv.FLEET]
        self.assertEqual(unplaced["status"], "failed")
        st = vr.Status(focused=True, fetching=(), now=__import__("datetime").datetime.now(), oldest=None, from_cache=False)
        rows = [vr.line_text(l) for l in rr.prs_lines([vr.Agent("a", "h", "agent", {"prs": rec})], unplaced, st, 0, 120, 10)[0]]
        self.assertTrue(any("not a placed agent's: not read: agent-fabric's fleet.py here does not list them" in r for r in rows))

    def test_a_section_fleet_does_not_serve_is_said_and_never_asked(self):
        from types import SimpleNamespace
        import queue
        fleet = SimpleNamespace(SECTIONS={"prs": SimpleNamespace(ttl=120)})
        view = fv.View(fleet, ("plans",), None, fv.Store(), queue.Queue())
        self.assertEqual(view.refresher.due(0, True), [])
        self.assertIn("serves no plans section", fv.fleet_record(view.store, "plans", view.whys)["why"])


if __name__ == "__main__":
    unittest.main()
