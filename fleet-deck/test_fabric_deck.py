import datetime
import json
import os
import shlex
import stat
import sys
import tempfile
import unittest

from deck_tabs import RESTORE_WAIT_S, RESUME, SAME_SESSION_S, SETTLE_S, WAIT, WATCH, Before, Shown, State, endpoint
from fabric_deck import (
    live_of,
    BOARD_DIR,
    PANE_MAP_REFRESH_S,
    NEW_WORKSPACE,
    UNBOUND,
    RESEND_AFTER_S,
    agent_view_command,
    is_agent_view,
    read_tab,
    PaneInfo,
    RESTORE_SETTLE_S,
    Account,
    Deck,
    Herdr,
    Session,
    StateRecord,
    Stream,
    for_this_host,
    harness_under,
    herdr_socket_path,
    account_command,
    label_commands,
    load_befores,
    modes_in,
    next_backoff,
    parse_moveto_list,
    parse_state_line,
    proc_argv,
    proc_parents,
    proc_ssh_endpoints,
    release_commands,
    report_command,
    save_befores,
    server_instance,
    start_ticks,
    seed_workspace,
    stop_child,
)

CATALOG = {
    "groups": ["Coordinator", "Rust Developer", "Experts"],
    "roles": [
        {"id": "fabric-coordinator", "group": "Coordinator"},
        {"id": "rust-ui-dev", "group": "Rust Developer"},
        {"id": "language-culture", "group": "Experts"},
        {"id": "orphan-role", "group": "A group the catalogue does not list"},
    ],
}

NOW = datetime.datetime(2026, 10, 8, 9, 0, 0, tzinfo=datetime.timezone.utc)
SERVER, OTHER = (4242, 777), (4343, 999)
ENTER = "/usr/local/share/moveto/enter"


class ParseMovetoList(unittest.TestCase):
    def test_reads_account_and_role_and_skips_the_excluded_login(self):
        text = (
            "user               fabric-coordinator  agent-fabric\n"
            "rust-ui-dev-01     rust-ui-dev         herdr interweave\n"
            "\n"
            "lonely\n"
        )
        self.assertEqual(
            parse_moveto_list(text, exclude={"user"}),
            [Account("rust-ui-dev-01", "rust-ui-dev")],
        )


class Seed(unittest.TestCase):
    def test_a_role_goes_to_its_catalogue_group(self):
        self.assertEqual(seed_workspace("rust-ui-dev", CATALOG), "Rust Developer")

    def test_unlisted_role_unlisted_group_or_no_catalogue_go_to_new(self):
        self.assertEqual(seed_workspace("nobody", CATALOG), NEW_WORKSPACE)
        self.assertEqual(seed_workspace("orphan-role", CATALOG), NEW_WORKSPACE)
        self.assertEqual(seed_workspace("rust-ui-dev", None), NEW_WORKSPACE)


class Records(unittest.TestCase):
    def test_parses_a_stream_line_of_today(self):
        line = (
            '{"address":"develop-qzapp/ui","ts":"2026-10-08T05:00:31Z","role":"rust-ui-dev",'
            '"sessions":[{"session":"s1","state":"idle","since":"2026-10-08T05:00:30Z"}],'
            '"state":"idle","since":"2026-10-08T05:00:30Z"}'
        )
        parsed = parse_state_line(line)
        self.assertEqual(
            (parsed.login, parsed.host, [x.session for x in parsed.sessions]),
            ("ui", "develop-qzapp", ["s1"]),
        )
        self.assertIsNone(parse_state_line("not json"))

    def test_a_field_of_the_wrong_type_is_read_as_absent(self):
        ts = '"ts":"2026-10-08T05:00:00Z"'
        for line in ('[1]', '"x"', '{"address":5,%s}' % ts, '{"address":"h/ui","ts":5}'):
            self.assertIsNone(parse_state_line(line), line)
        odd = parse_state_line(
            '{"address":"h/ui",%s,"state":["working"],"last_session":7,"resumable":"yes",'
            '"sessions":[{"session":3},{"session":"s1","state":{},"since":9},"s2"]}' % ts
        )
        self.assertEqual((odd.state, odd.last_session, odd.resumable), ("", None, None))
        self.assertEqual(odd.sessions, (Session("s1", "unknown", ""),))
        self.assertEqual(parse_state_line('{"address":"h/ui",%s,"sessions":{}}' % ts).sessions, ())

    def test_a_blocked_sessions_reason_is_kept_only_as_a_known_word(self):
        ts = '"ts":"2026-10-08T05:00:00Z"'
        parsed = parse_state_line(
            '{"address":"h/ui",%s,"sessions":[{"session":"s1","state":"blocked","reason":"permission"},'
            '{"session":"s2","state":"blocked","reason":"\\u001b[2J"},{"session":"s3","state":"blocked","reason":7},'
            '{"session":"s4","state":"blocked","reason":["permission"]},{"session":"s5","state":"blocked","reason":{}}]}' % ts
        )
        # An unhashable value tested against the set would raise and drop the account's record.
        self.assertEqual([x.reason for x in parsed.sessions], ["permission", None, None, None, None])

    def test_a_sessions_ssh_client_is_kept_only_as_an_address_and_a_port(self):
        ts = '"ts":"2026-10-08T05:00:00Z"'
        clients = ('{"addr":"127.0.0.1","port":40001}', '{"addr":"::ffff:127.0.0.1","port":40001}',
                   '{"addr":"::1","port":22}', '{"addr":"127.0.0.1","port":"40001"}',
                   '{"addr":"127.0.0.1","port":true}', '{"addr":"127.0.0.1","port":0}',
                   '{"addr":"127.0.0.1","port":65536}', '{"addr":"localhost","port":22}',
                   '{"addr":7,"port":22}', '["127.0.0.1",22]', '"127.0.0.1 40001"', 'null')
        parsed = parse_state_line('{"address":"h/ui",%s,"sessions":[%s]}' % (ts, ",".join(
            '{"session":"s%d","state":"working","ssh_client":%s}' % (i, c) for i, c in enumerate(clients))))
        got = [x.ssh_client for x in parsed.sessions]
        self.assertEqual(got[0], endpoint("127.0.0.1", 40001))
        self.assertEqual(got[1], got[0], "an IPv4-mapped address is its IPv4 form")
        self.assertEqual(got[2], endpoint("::1", 22))
        self.assertEqual(got[3:], [None] * (len(clients) - 3))
        self.assertIsNone(parse_state_line('{"address":"h/ui",%s,"sessions":[{"session":"s"}]}' % ts)
                          .sessions[0].ssh_client, "absent on a session not entered over ssh")

    def test_the_streams_no_record_row_is_no_record(self):
        # ctl.mjs stateRow for an account with nothing on the channel: no ts.
        row = ('{"address":"develop-qzapp/ui","role":"rust-ui-dev","state":"unknown",'
               '"sessions":[],"why":"no state record on the channel"}')
        self.assertIsNone(parse_state_line(row))
        self.assertIsNone(parse_state_line('{"address":"develop-qzapp/ui","ts":"yesterday"}'))
        self.assertIsNone(parse_state_line('{"address":"develop-qzapp/ui","ts":"2026-10-08T05:00:00"}'))

    def test_the_stream_filter_keeps_only_this_hosts_records(self):
        here = StateRecord("ui", "idle", (), "2026-10-08T05:00:00Z", host="host-a")
        there = StateRecord("ui", "idle", (), "2026-10-08T05:00:00Z", host="host-b")
        self.assertTrue(for_this_host(here, "host-a"))
        self.assertFalse(for_this_host(there, "host-a"))
        self.assertTrue(for_this_host(there, None), "an unknown host takes every record")
        self.assertFalse(for_this_host(None, "host-a"))


def record(login, *states, age_s=10):
    ts = (NOW - datetime.timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sessions = tuple(Session(f"s{i}", s, ts) for i, s in enumerate(states))
    return StateRecord(login, states[0] if states else "none", sessions, ts, host="h")


def ssh_record(login, *sessions, age_s=10):
    """A record of (state, (addr, port) or None) sessions: the endpoint is the
    `ssh_client` a session enter-ssh started carries."""
    ts = (NOW - datetime.timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = tuple(Session(f"s{i}", state, ts, ssh_client=None if client is None else endpoint(*client))
                 for i, (state, client) in enumerate(sessions))
    return StateRecord(login, sessions[0][0], rows, ts, host="h")


PANE_END = ("127.0.0.1", 40001)
# Every start's mark, fixed for the tests (setUpModule).
MARK = "m1"
# What the deck types into the agent pane of ui's tab.
VIEW = agent_view_command("ui", start=MARK)


# view_lock is taken here, never beside a running deck's.
LOCK_DIR = tempfile.TemporaryDirectory()


_REAL_MARK = None


def setUpModule():
    global _REAL_MARK
    import fabric_deck
    _REAL_MARK, fabric_deck.new_mark = fabric_deck.new_mark, lambda: MARK


def tearDownModule():
    import fabric_deck
    fabric_deck.new_mark = _REAL_MARK
    LOCK_DIR.cleanup()


BARE = {"shell_pid": 10, "foreground_process_group_id": 10,
        "foreground_processes": [{"pid": 10, "argv": ["bash"]}]}
# The fleet board, as fabric-view's launcher leaves it in its pane.
BOARD = {"shell_pid": 30, "foreground_process_group_id": 30, "foreground_processes": [{"pid": 30, "argv": [
    "/usr/local/bin/fabric-python", "-B", "-c",
    "import sys; sys.path.insert(0, sys.argv[1]); from fabric_view import main; raise SystemExit(main(sys.argv[2:]))",
    "/home/user/projects/herdr/fleet-deck", "board"]}]}
# A shell still running the operator's rc file: neither bare nor moveto.
BUSY = {"shell_pid": 10, "foreground_process_group_id": 11,
        "foreground_processes": [{"pid": 11, "argv": ["direnv", "hook"]}]}


def in_moveto(login, mode="", pid=20):
    argv = ["sudo", "-n", "-u", login, "-H", ENTER, f"/home/{login}/projects", login]
    return {"shell_pid": 10, "foreground_process_group_id": pid,
            "foreground_processes": [{"pid": pid, "argv": argv + ([mode] if mode else [])}]}


def in_view(login, pid=40):
    """The agent's screen the deck started in the tab's agent pane."""
    argv = ["/usr/local/bin/fabric-python", "-B", "-c", BOARD["foreground_processes"][0]["argv"][3],
            "/home/user/projects/herdr/fleet-deck", "agent", "--agent", login, "--in-tab"]
    return {"shell_pid": 10, "foreground_process_group_id": pid,
            "foreground_processes": [{"pid": pid, "argv": argv}]}


def in_ssh(login, word, pid=20):
    """moveto --via ssh: the operator's ssh into the account's forced command."""
    argv = ["ssh", "-t", "-i", "/home/user/.ssh/fabric_deck", f"{login}@127.0.0.1", "--", word]
    return {"shell_pid": 10, "foreground_process_group_id": pid,
            "foreground_processes": [{"pid": pid, "argv": argv}]}


class FakeHerdr(Herdr):
    """herdr's server as the deck's calls see it: workspaces, tabs, labelled
    panes and each pane's process info, every call recorded. The adapter's
    own account_tabs and process_info run on top of it."""

    def __init__(self):
        super().__init__(binary="herdr")
        self.workspace_list = [{"workspace_id": "w1", "label": "New"}]
        self.tabs = {"w1": []}
        self.panes = {}
        self.proc = {}
        self.calls = []
        self.down = False
        self.n = 0
        self.new_pane = BARE
        self.workspace_lists_ok = None  # after this many, `workspace list` fails
        self.fail_once = set()  # (subcommand, pane) pairs whose next call fails
        self.agent_status = {}  # pane -> the state herdr holds from the deck's reports
        self.drops_reports = set()  # panes whose reports herdr answers but does not apply
        self.plugin_linked = True
        self.tab_move = True  # False: a FleetDeck from before tab.move_to_workspace
        self.zoom_in_tab = True  # False: a FleetDeck from before pane.zoom_in_tab

    def _id(self, kind):
        # Never one a test named by hand (p0, p1, p2...): a split must not
        # take over a pane the test set up.
        while True:
            self.n += 1
            made = f"{kind}{self.n}"
            if made not in self.panes and not any(t["tab_id"] == made for tabs in self.tabs.values() for t in tabs):
                return made

    def add_tab(self, label, panes, workspace="w1"):
        tab = self._id("t")
        self.tabs[workspace].append({"tab_id": tab, "label": label})
        for pane, pane_label, info in panes:
            self.panes[pane] = {"pane_id": pane, "tab_id": tab, "label": pane_label}
            self.proc[pane] = info
        return tab

    def runs(self, pane=None):
        return [c[3] for c in self.calls if c[:2] == ("pane", "run") and (pane is None or c[2] == pane)]

    def reports(self, pane):
        return [c for c in self.calls if c[1] in ("report-agent", "report-metadata") and c[2] == pane]

    def call(self, *args):
        if self.down:
            raise ConnectionError("herdr's socket refuses")
        self.calls.append(args)
        head = args[:2]
        target = args[3] if head == ("pane", "process-info") else (args[2] if len(args) > 2 else None)
        if (head[1], target) in self.fail_once:
            self.fail_once.discard((head[1], target))
            raise RuntimeError(f"herdr {' '.join(args)}: exit 1: server_unavailable")
        if head == ("workspace", "list"):
            if self.workspace_lists_ok is not None:
                if self.workspace_lists_ok == 0:
                    raise RuntimeError("herdr workspace list: exit 1: not ready")
                self.workspace_lists_ok -= 1
            return {"workspaces": list(self.workspace_list)}
        if head == ("workspace", "create"):
            # Its own prefix: a seeded workspace is w1, and a created one
            # sharing the counter would collide with it.
            w = self._id("ws")
            self.workspace_list.append({"workspace_id": w, "label": args[3]})
            self.tabs[w] = []
            return {"workspace": {"workspace_id": w}, "tab": {"tab_id": self.add_tab(None, [], w)}}
        if head == ("tab", "list"):
            return {"tabs": list(self.tabs[args[3]])}
        if head == ("tab", "create"):
            pane = self._id("p")
            tab = self.add_tab(args[args.index("--label") + 1], [(pane, None, self.new_pane)], args[3])
            return {"tab": {"tab_id": tab}, "root_pane": {"pane_id": pane}}
        if head == ("tab", "close"):
            for tabs in self.tabs.values():
                tabs[:] = [t for t in tabs if t["tab_id"] != args[2]]
            return {}
        if head == ("pane", "list"):
            return {"panes": list(self.panes.values())}
        if head == ("pane", "split"):
            pane = self._id("p")
            self.panes[pane] = {"pane_id": pane, "tab_id": self.panes[args[2]]["tab_id"], "label": None}
            self.proc[pane] = self.new_pane
            return {"pane": {"pane_id": pane}}
        if head == ("pane", "rename"):
            self.panes[args[2]]["label"] = args[3]
            return {}
        if head == ("pane", "process-info"):
            return {"process_info": self.proc[args[3]]}
        if head == ("pane", "report-agent") and args[2] not in self.drops_reports:
            self.agent_status[args[2]] = args[args.index("--state") + 1]
        if head == ("pane", "get"):
            return {"pane": {**self.panes[args[2]], "agent": "claude",
                             "agent_status": self.agent_status.get(args[2], "unknown")}}
        if head[0] == "pane" and head[1] in ("run", "send-text", "report-agent", "report-metadata", "release-agent"):
            return {}
        if args[:3] == ("plugin", "pane", "open"):
            if not self.plugin_linked:
                raise RuntimeError("herdr plugin pane open: exit 1: plugin_not_found")
            pane = self._id("p")
            tab = self.add_tab(None, [(pane, None, BOARD)], args[args.index("--workspace") + 1])
            return {"plugin_pane": {"plugin_id": args[4], "entrypoint": args[6],
                                    "pane": {"pane_id": pane, "tab_id": tab}}}
        if head == ("tab", "move"):
            if not self.tab_move:
                raise RuntimeError("herdr tab move: exit 1: unknown method tab.move_to_workspace")
            target = args[args.index("--workspace") + 1]
            moved = next(t for tabs in self.tabs.values() for t in tabs if t["tab_id"] == args[2])
            for tabs in self.tabs.values():
                tabs[:] = [t for t in tabs if t is not moved]
            # As FleetDeck does: the tab and its panes get the target's ids.
            new_tab = self._id("t")
            self.tabs[target].append({"tab_id": new_tab, "label": moved["label"]})
            for old in [p for p, pane in self.panes.items() if pane["tab_id"] == args[2]]:
                new = self._id("p")
                self.panes[new] = dict(self.panes.pop(old), pane_id=new, tab_id=new_tab)
                self.proc[new] = self.proc.pop(old)
            return {"tab": {"tab_id": new_tab, "workspace_id": target}}
        if head == ("pane", "zoom"):
            if "--in-tab" in args and not self.zoom_in_tab:
                raise RuntimeError("herdr pane zoom: exit 1: unknown method pane.zoom_in_tab")
            return {}
        if head == ("tab", "rename"):
            for tabs in self.tabs.values():
                for tab in tabs:
                    if tab["tab_id"] == args[2]:
                        tab["label"] = args[3]
            return {}
        raise AssertionError(f"unexpected herdr call {args}")


ALL_MODES = frozenset({WAIT, WATCH, RESUME})


class Harness:
    """A deck over a FakeHerdr, with the stream's records, a /proc tree and
    the record of what was shown as plain values a test sets."""

    def __init__(self, herdr=None, logins=("ui",), modes=ALL_MODES, befores=None, fleet_tab=False,
                 roles=None, catalog=None):
        self.herdr = herdr or FakeHerdr()
        self.records = {}
        self.tree, self.argvs = {}, {}
        # pid -> the client ends of that ssh's connections, as /proc gives them
        self.sockets = {}
        self.store = None if befores is None else dict(befores)
        self.logs = []
        self.logins = list(logins)
        # moveto --list's role per login: rust-ui-dev unless a test says.
        self.roles = dict(roles or {})
        self.instance = SERVER
        self.wall = NOW

        def save(befores):
            self.store = dict(befores)

        self.deck = Deck(
            herdr=self.herdr,
            accounts=lambda: [Account(login, self.roles.get(login, "rust-ui-dev")) for login in self.logins],
            records=self.records,
            modes=modes,
            cwd="/c",
            catalog=catalog,
            parents=lambda: dict(self.tree),
            argv=lambda pid: self.argvs.get(pid, []),
            ssh_endpoints=lambda pid: self.sockets.get(pid),
            load=lambda: None if self.store is None else dict(self.store),
            save=save,
            server=lambda: None if self.herdr.down else self.instance,
            log=self.logs.append,
            utc=lambda: self.wall,
            # The account tabs' tests count herdr calls: the fleet tab is
            # tested on its own (FleetTab).
            fleet_tab=fleet_tab,
            lock_dir=LOCK_DIR.name,
            sleep=lambda s: None,
        )

    def at(self, deck_s):
        """The deck's clock and the wall clock, moved together."""
        self.wall = NOW + datetime.timedelta(seconds=deck_s)
        return deck_s

    def harness_runs(self, pane, login="ui", mode=WAIT):
        """A person pressed Enter: moveto holds the pane, a harness under it."""
        self.herdr.proc[pane] = in_moveto(login, mode)
        self.tree.update({21: 20, 22: 21})
        self.argvs[22] = ["claude", "--model", "x"]


def harness_of(h, login="ui"):
    return h.deck.harness_pane[login]


class FleetTab(unittest.TestCase):
    def tabs(self, h):
        return [(w, t["label"]) for w, ts in h.herdr.tabs.items() for t in ts]

    def test_a_restore_opens_the_board_as_a_tab_labelled_fleet_once(self):
        h = Harness(fleet_tab=True)
        h.deck.restore(0)
        opened = [c for c in h.herdr.calls if c[:3] == ("plugin", "pane", "open")]
        self.assertEqual(len(opened), 1)
        self.assertIn("--no-focus", opened[0])
        self.assertEqual(opened[0][opened[0].index("--entrypoint") + 1], "board")
        self.assertIn(("w1", "fleet"), self.tabs(h))
        h.deck.restore(10)
        self.assertEqual(len([c for c in h.herdr.calls if c[:3] == ("plugin", "pane", "open")]), 1)

    def test_a_fleet_tab_running_the_board_anywhere_is_kept_and_none_is_added(self):
        h = Harness(fleet_tab=True)
        h.herdr.workspace_list.append({"workspace_id": "w9", "label": "Ops"})
        h.herdr.tabs["w9"] = []
        h.herdr.add_tab("fleet", [("p90", None, BOARD)], "w9")
        h.deck.restore(0)
        self.assertFalse([c for c in h.herdr.calls if c[:3] == ("plugin", "pane", "open")])

    def test_a_fleet_tab_herdr_brought_back_as_a_bare_shell_gets_the_board_again(self):
        # Measured on a real herdr: a session restore keeps the tab's label
        # and gives its pane a shell, not the plugin's program.
        h = Harness(fleet_tab=True)
        old = h.herdr.add_tab("fleet", [("p90", None, BARE)])
        h.herdr.panes["p90"]["cwd"] = BOARD_DIR
        h.deck.restore(0)
        self.assertIn(("tab", "close", old), h.herdr.calls)
        self.assertEqual(len([c for c in h.herdr.calls if c[:3] == ("plugin", "pane", "open")]), 1)
        self.assertEqual([t for _, t in self.tabs(h)].count("fleet"), 1)

    def test_a_persons_shell_tab_named_fleet_elsewhere_is_never_closed(self):
        h = Harness(fleet_tab=True)
        tab = h.herdr.add_tab("fleet", [("p90", None, BARE)])
        h.herdr.panes["p90"]["cwd"] = "/home/user/projects"
        h.deck.restore(0)
        self.assertNotIn(("tab", "close", tab), h.herdr.calls)
        self.assertFalse([c for c in h.herdr.calls if c[0] == "plugin"])

    def test_a_fleet_tab_whose_shell_has_not_started_is_looked_at_again_at_the_next_map_read(self):
        h = Harness(fleet_tab=True)
        tab = h.herdr.add_tab("fleet", [("p90", None, {"shell_pid": None, "foreground_processes": []})])
        h.herdr.panes["p90"]["cwd"] = BOARD_DIR
        h.deck.restore(0)
        self.assertNotIn(("tab", "close", tab), h.herdr.calls)
        self.assertFalse([l for l in h.logs if "something else" in l])
        h.herdr.proc["p90"] = BARE
        h.deck.follow(PANE_MAP_REFRESH_S + 1)
        self.assertIn(("tab", "close", tab), h.herdr.calls)
        self.assertEqual(len([c for c in h.herdr.calls if c[:3] == ("plugin", "pane", "open")]), 1)

    def test_an_unsettled_fleet_tab_a_person_closes_is_not_reopened_before_the_next_restore(self):
        h = Harness(fleet_tab=True)
        tab = h.herdr.add_tab("fleet", [("p90", None, {"shell_pid": None, "foreground_processes": []})])
        h.herdr.panes["p90"]["cwd"] = BOARD_DIR
        h.deck.restore(0)
        h.herdr.call("tab", "close", tab)
        h.deck.follow(PANE_MAP_REFRESH_S + 1)
        h.deck.follow(2 * PANE_MAP_REFRESH_S + 2)
        self.assertFalse([c for c in h.herdr.calls if c[:3] == ("plugin", "pane", "open")])

    def test_herdr_failing_while_an_unsettled_fleet_tab_is_looked_at_again_leaves_the_deck_running(self):
        h = Harness(fleet_tab=True)
        h.herdr.add_tab("fleet", [("p90", None, {"shell_pid": None, "foreground_processes": []})])
        h.herdr.panes["p90"]["cwd"] = BOARD_DIR
        h.deck.restore(0)
        tabs = h.herdr.account_tabs

        def then_down(logins):
            got = tabs(logins)
            h.herdr.down = True        # the server goes between the map read and the look
            return got
        h.herdr.account_tabs = then_down
        h.deck.follow(PANE_MAP_REFRESH_S + 1)   # must not raise
        self.assertIsNotNone(h.deck.fleet_unsettled)   # looked at again once herdr answers
        h.herdr.down = False
        h.herdr.account_tabs = tabs
        h.herdr.proc["p90"] = BARE
        h.deck.follow(2 * PANE_MAP_REFRESH_S + 2)
        self.assertEqual(len([c for c in h.herdr.calls if c[:3] == ("plugin", "pane", "open")]), 1)

    def test_a_fleet_tab_running_something_else_is_left_alone_and_said_once(self):
        h = Harness(fleet_tab=True)
        tab = h.herdr.add_tab("fleet", [("p90", None, in_moveto("ui"))])
        h.deck.restore(0)
        h.deck.restore(10)
        self.assertNotIn(("tab", "close", tab), h.herdr.calls)
        self.assertFalse([c for c in h.herdr.calls if c[0] == "plugin"])
        self.assertEqual(sum("runs something else" in l for l in h.logs), 1)

    def test_an_account_only_restore_leaves_the_fleet_tab_alone(self):
        h = Harness(fleet_tab=True)
        h.deck.restore(0, only={"ui"})
        self.assertFalse([c for c in h.herdr.calls if c[0] == "plugin"])

    def test_a_plugin_not_linked_is_said_once_and_the_accounts_are_restored(self):
        h = Harness(fleet_tab=True)
        h.herdr.plugin_linked = False
        h.deck.restore(0)
        h.deck.restore(10)
        said = [l for l in h.logs if "no fleet tab" in l]
        self.assertEqual(len(said), 1)
        self.assertIn("agent-fabric-fleetdeck plugin link", said[0])
        self.assertIn(("w1", "ui"), self.tabs(h))
        self.assertNotIn(("w1", "fleet"), self.tabs(h))


def fabric_deck_mode_view():
    import fabric_deck
    return fabric_deck.VIEW  # the waiting mode, not the typed command VIEW


def four_panes(login, prefix):
    return [(f"{prefix}0", "harness", in_moveto(login, WAIT)), (f"{prefix}1", "shell", in_moveto(login)),
            (f"{prefix}2", "status", in_moveto(login, WATCH)), (f"{prefix}3", "agent", in_view(login))]


class ToRoleWorkspace(unittest.TestCase):
    def herdr(self):
        herdr = FakeHerdr()
        herdr.workspace_list.append({"workspace_id": "w9", "label": "Rust Developer"})
        herdr.tabs["w9"] = []
        return herdr

    def test_a_tab_in_new_is_moved_to_its_roles_workspace_and_followed_there(self):
        herdr = self.herdr()
        herdr.add_tab("ui", four_panes("ui", "q"))
        h = Harness(herdr, catalog=CATALOG)
        h.deck.restore(0)
        self.assertEqual([t["label"] for t in herdr.tabs["w1"]], [])
        self.assertEqual([t["label"] for t in herdr.tabs["w9"]], ["ui"])
        harness = harness_of(h)
        self.assertEqual(herdr.panes[harness]["label"], "harness")
        self.assertNotIn(harness, ("q0", "q1", "q2"), "followed by its ids after the move")
        self.assertEqual(h.deck.harness_pane["ui"], harness)
        self.assertEqual(h.logs.count("ui: moved its tab from New to Rust Developer"), 1)

    def test_a_tab_a_person_put_elsewhere_or_a_role_without_a_workspace_stays(self):
        herdr = self.herdr()
        herdr.workspace_list.append({"workspace_id": "w8", "label": "Ops"})
        herdr.tabs["w8"] = []
        herdr.add_tab("ui", four_panes("ui", "q"), "w8")
        herdr.add_tab("coord", four_panes("coord", "c"))
        h = Harness(herdr, logins=("ui", "coord"), roles={"coord": "fabric-coordinator"}, catalog=CATALOG)
        h.deck.restore(0)
        self.assertFalse(any(c[:2] == ("tab", "move") for c in herdr.calls),
                         "Ops is a person's choice; Coordinator does not exist here")

    def test_duplicate_labels_resolve_to_the_first_as_tabs_are_made_there(self):
        herdr = self.herdr()
        herdr.workspace_list.append({"workspace_id": "w7", "label": "Rust Developer"})
        herdr.tabs["w7"] = []
        herdr.workspace_list.append({"workspace_id": "w6", "label": "New"})
        herdr.tabs["w6"] = []
        herdr.add_tab("ui", four_panes("ui", "q"))
        h = Harness(herdr, catalog=CATALOG)
        h.deck.restore(0)
        self.assertEqual([t["label"] for t in herdr.tabs["w9"]], ["ui"], "the first Rust Developer")
        self.assertEqual(herdr.tabs["w7"], [])

    def test_a_fleetdeck_without_tab_move_leaves_the_tab_and_says_so_once(self):
        herdr = self.herdr()
        herdr.tab_move = False
        herdr.add_tab("ui", four_panes("ui", "q"))
        h = Harness(herdr, catalog=CATALOG)
        h.deck.restore(0)
        h.deck.restore(1)
        self.assertEqual([t["label"] for t in herdr.tabs["w1"]], ["ui"])
        self.assertEqual(h.deck.harness_pane["ui"], "q0")
        self.assertEqual(sum("its tab stays in New" in line for line in h.logs), 1)


    def test_a_restore_shows_the_harness_alone_without_switching_tabs(self):
        herdr = self.herdr()
        herdr.add_tab("ui", four_panes("ui", "q"))
        h = Harness(herdr, catalog=CATALOG)
        h.deck.restore(0)
        zooms = [c for c in herdr.calls if c[:2] == ("pane", "zoom")]
        harness = h.deck.harness_pane["ui"]
        self.assertEqual(herdr.panes[harness]["label"], "harness")
        self.assertEqual(zooms, [("pane", "zoom", harness, "--on", "--in-tab")])

    def test_a_tab_with_a_pane_of_its_own_is_not_shown_one_pane_at_a_time(self):
        herdr = self.herdr()
        herdr.add_tab("ui", [*four_panes("ui", "q"), ("q9", None, BARE)])
        h = Harness(herdr, catalog=CATALOG)
        h.deck.restore(0)
        self.assertFalse(any(c[:2] == ("pane", "zoom") for c in herdr.calls),
                         "no second row there, so all its panes stay in sight")

    def test_a_retried_restore_leaves_the_pane_the_person_picked(self):
        herdr = self.herdr()
        herdr.add_tab("ui", four_panes("ui", "q"))
        h = Harness(herdr, catalog=CATALOG)
        h.deck.restore(0)
        h.deck.restore(1, only={"ui"})
        self.assertEqual(len([c for c in herdr.calls if c[:2] == ("pane", "zoom")]), 1)

    def test_a_fleetdeck_without_zoom_in_tab_still_restores_and_says_so_once(self):
        herdr = self.herdr()
        herdr.zoom_in_tab = False
        herdr.add_tab("ui", four_panes("ui", "q"))
        h = Harness(herdr, catalog=CATALOG)
        h.deck.restore(0)
        h.deck.restore(1)
        self.assertEqual(herdr.panes[h.deck.harness_pane["ui"]]["label"], "harness")
        said = [line for line in h.logs if "shows every pane" in line]
        self.assertEqual(len(said), 1, "said once")
        self.assertIn("pane.zoom_in_tab", said[0], "with the error itself")


class Restore(unittest.TestCase):
    def test_an_account_with_no_role_bound_gets_its_tab_in_its_roles_workspace_once_bound(self):
        h = Harness(roles={"ui": UNBOUND}, catalog=CATALOG)
        h.deck.restore(0)
        self.assertFalse(any(c[:2] == ("tab", "create") for c in h.herdr.calls), "no tab in New for good")
        h.deck.follow(h.at(PANE_MAP_REFRESH_S + 1))
        self.assertEqual(sum("no role bound yet" in line for line in h.logs), 1, "said once")
        h.roles["ui"] = "rust-ui-dev"
        h.deck.follow(h.at(2 * PANE_MAP_REFRESH_S + 2))
        create = next(c for c in h.herdr.calls if c[:2] == ("tab", "create"))
        workspace = create[create.index("--workspace") + 1]
        labels = {w["workspace_id"]: w["label"] for w in h.herdr.workspace_list}
        self.assertEqual(labels[workspace], "Rust Developer")

    def test_an_account_that_waited_through_first_setup_is_seeded_as_on_first_setup(self):
        h = Harness(logins=("ui", "coord"), roles={"coord": UNBOUND}, catalog=CATALOG)
        h.deck.restore(0)
        h.roles["coord"] = "fabric-coordinator"
        h.deck.follow(h.at(PANE_MAP_REFRESH_S + 1))
        labels = {w["workspace_id"]: w["label"] for w in h.herdr.workspace_list}
        made = {c[c.index("--label") + 1]: labels[c[c.index("--workspace") + 1]]
                for c in h.herdr.calls if c[:2] == ("tab", "create")}
        self.assertEqual(made, {"ui": "Rust Developer", "coord": "Coordinator"},
                         "the others' tabs since do not make it a later account")

    def test_an_account_no_longer_placed_does_not_keep_its_first_setup_seeding(self):
        h = Harness(logins=("ui", "coord"), roles={"coord": UNBOUND}, catalog=CATALOG)
        h.deck.restore(0)
        h.logins.remove("coord")
        h.deck.follow(h.at(PANE_MAP_REFRESH_S + 1))
        self.assertEqual(h.deck.seed_on_bind, set())

    def test_a_new_account_gets_a_four_pane_tab_its_harness_waiting_for_the_decision(self):
        h = Harness()
        h.deck.restore(0)
        labels = sorted(p["label"] for p in h.herdr.panes.values())
        self.assertEqual(labels, ["agent", "harness", "shell", "status"])
        harness = harness_of(h)
        self.assertEqual(h.herdr.panes[harness]["label"], "harness")
        splits = [c for c in h.herdr.calls if c[:2] == ("pane", "split")]
        self.assertEqual((splits[0][2], splits[0][4], splits[0][6]), (harness, "right", "0.65"))
        status = next(p for p, pane in h.herdr.panes.items() if pane["label"] == "status")
        self.assertEqual((splits[2][2], splits[2][4]), (status, "down"), "the agent pane below the status")
        h.deck.follow(1)
        self.assertEqual(sorted(h.herdr.runs()), sorted(["moveto ui", "moveto ui --watch", VIEW]))
        self.assertEqual(h.herdr.runs(harness), [], "the harness waits for the stream")

    def test_panes_still_busy_when_created_wait_for_their_prompt_and_the_decision(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.herdr.new_pane = BUSY
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(h.at(RESTORE_SETTLE_S))
        self.assertEqual(h.herdr.runs(), [], "nothing is typed into a busy pane")
        self.assertEqual(h.deck.pending.keys(), {"ui"})
        for pane in h.herdr.panes:
            h.herdr.proc[pane] = BARE
        h.deck.follow(h.at(RESTORE_SETTLE_S + 2))
        self.assertEqual(sorted(h.herdr.runs()), sorted([VIEW, "moveto ui", "moveto ui --resume", "moveto ui --watch"]))
        h.deck.follow(h.at(60))
        self.assertEqual(h.store, {"ui": Before(running=True)}, "the fall from before the decision is never noted")

    def test_a_harness_busy_past_the_wait_still_gets_the_restore_decision(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.herdr.new_pane = BUSY
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        for at in range(1, RESTORE_WAIT_S + 10, 2):
            h.deck.follow(h.at(at))
        self.assertEqual(h.herdr.runs(), [])
        self.assertEqual(sum("still busy" in line for line in h.logs), 4, "said once per pane")
        for pane in h.herdr.panes:
            h.herdr.proc[pane] = BARE
        h.deck.follow(h.at(RESTORE_WAIT_S + 12))
        self.assertIn("moveto ui --resume", h.herdr.runs(harness_of(h)))

    def test_shell_and_status_panes_already_running_moveto_are_not_waited_for(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", "harness", in_moveto("ui", WAIT)), ("p1", "shell", in_moveto("ui")),
                             ("p2", "status", in_moveto("ui", WATCH)), ("p3", "agent", in_view("ui"))])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(1)
        self.assertEqual(h.deck.waiting, {}, "dropped at the first look")
        for at in range(1, RESTORE_WAIT_S + 10, 2):
            h.deck.follow(at)
        self.assertFalse(any("busy" in line for line in h.logs))

    def test_a_restore_that_keeps_failing_is_said_once(self):
        h = Harness()
        h.deck.restore(0)
        h.herdr.down = True
        h.deck.follow(10)
        h.herdr.down = False
        # The map reads and the restore's own tab read pass; its listing fails.
        h.herdr.workspace_lists_ok = 2
        for at in range(20, 40, 2):
            h.deck.follow(at)
            h.herdr.workspace_lists_ok = 2
        self.assertEqual(sum(line.startswith("cannot restore yet") for line in h.logs), 1)
        self.assertEqual(h.logs.count("herdr's server answers: restoring"), 1)
        h.herdr.workspace_lists_ok = None
        h.deck.follow(50)
        self.assertFalse(h.deck.lost)
        h.instance = OTHER  # a later restart is said again
        h.deck.follow(52)
        self.assertEqual(h.logs.count("herdr's server answers: restoring"), 2)

    def test_a_failed_look_at_a_pane_during_restore_still_leaves_the_decision_to_come(self):
        for failing in ("p1", "p3", "p4", "p5"):  # the harness, the shell, the status, the agent pane
            h = Harness(befores={"ui": Before(running=True)})
            h.records["ui"] = record("ui")
            h.herdr.fail_once = {("process-info", failing)}
            h.deck.restore(0)
            for at in range(1, PANE_MAP_REFRESH_S + RESTORE_SETTLE_S + 4, 2):
                h.deck.follow(h.at(at))
            self.assertFalse(h.herdr.fail_once, f"{failing}'s look failed once")
            harness = harness_of(h)
            self.assertEqual(h.herdr.runs(harness)[:1], ["moveto ui --resume"], f"{failing}: the decision")
            others = sorted(r for c, r in ((c, c[3]) for c in h.herdr.calls if c[:2] == ("pane", "run"))
                            if c[2] != harness)
            self.assertEqual(others, sorted([VIEW, "moveto ui", "moveto ui --watch"]), failing)

    def test_an_account_whose_restore_failed_part_way_is_restored_again(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.records["ui"] = record("ui")
        h.herdr.fail_once = {("split", "p1")}
        h.deck.restore(0)
        self.assertEqual(h.deck.retry, {"ui"})
        self.assertEqual((h.deck.harness_pane, h.deck.pending, h.deck.waiting), ({}, {}, {}),
                         "nothing of the half-done restore is followed")
        h.deck.follow(h.at(RESTORE_SETTLE_S))
        self.assertEqual(h.herdr.runs(), [], "no decision before the retry")
        h.deck.follow(h.at(PANE_MAP_REFRESH_S))
        h.deck.follow(h.at(PANE_MAP_REFRESH_S + RESTORE_SETTLE_S))
        h.deck.follow(h.at(PANE_MAP_REFRESH_S + RESTORE_SETTLE_S + 2))
        self.assertEqual(h.deck.retry, set())
        self.assertEqual(sorted(p["label"] for p in h.herdr.panes.values()), ["agent", "harness", "shell", "status"])
        self.assertIn("moveto ui --resume", h.herdr.runs(harness_of(h)))

    def test_during_a_boot_a_retried_decision_still_waits(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.deck.booting = lambda: True
        h.records["ui"] = record("ui")
        h.herdr.fail_once = {("split", "p1")}
        h.deck.restore(0)
        for t in (RESTORE_SETTLE_S, PANE_MAP_REFRESH_S, PANE_MAP_REFRESH_S + RESTORE_SETTLE_S,
                  PANE_MAP_REFRESH_S + RESTORE_SETTLE_S + 2):
            h.deck.follow(h.at(t))
        self.assertEqual(h.deck.retry, set())
        self.assertNotIn("moveto ui --resume", h.herdr.runs(harness_of(h)))
        self.assertIn("moveto ui --wait", h.herdr.runs(harness_of(h)))

    def test_a_restart_during_the_boot_still_waits_and_one_after_it_resumes(self):
        booting = [True]
        h = Harness(befores={"ui": Before(running=True)})
        h.deck.booting = lambda: booting[0]
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(harness_of(h)), ["moveto ui --wait"])
        # herdr restarts while the boot still waits on an earlier tier.
        self.assertEqual(self.restart_herdr(h, 100), ["moveto ui", "moveto ui --watch", VIEW, "moveto ui --wait"])
        booting[0] = False                # the boot has ended
        self.assertEqual(self.restart_herdr(h, 200), ["moveto ui", "moveto ui --watch", VIEW, "moveto ui --resume"])

    @staticmethod
    def restart_herdr(h, start):
        """One poll's outage, then follow until the restore's decision; the runs since."""
        before = len(h.herdr.runs())
        h.herdr.down = True
        h.deck.follow(start)
        h.herdr.down = False
        for t in range(start + 1, start + 2 + RESTORE_SETTLE_S):
            h.deck.follow(t)
        return h.herdr.runs()[before:]

    def test_an_account_that_leaves_the_list_is_not_retried(self):
        h = Harness()
        h.herdr.fail_once = {("split", "p1")}
        h.deck.restore(0)
        h.logins = []
        h.deck.follow(PANE_MAP_REFRESH_S)
        self.assertEqual(h.deck.retry, set())

    def test_an_account_placed_while_the_deck_runs_gets_its_tab(self):
        h = Harness(logins=("ui",))
        h.records.update(ui=record("ui"), vo=record("vo"))
        h.deck.restore(0)
        h.logins.append("vo")
        h.deck.follow(h.at(PANE_MAP_REFRESH_S))
        h.deck.follow(h.at(PANE_MAP_REFRESH_S + RESTORE_SETTLE_S))
        self.assertIn("vo", h.deck.harness_pane)
        self.assertIn("moveto vo --wait", h.herdr.runs(harness_of(h, "vo")))

    def test_a_harness_closed_by_hand_is_not_recreated_before_a_restore(self):
        h = Harness()
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        del h.herdr.panes[harness_of(h)]
        for at in range(PANE_MAP_REFRESH_S, 4 * PANE_MAP_REFRESH_S, 2):
            h.deck.follow(at)
        self.assertEqual(sum(c[:2] == ("pane", "split") for c in h.herdr.calls), 3, "only the first restore's")
        self.assertNotIn("ui", h.deck.harness_pane)

    def test_a_herdr_failure_while_restoring_leaves_the_deck_waiting_not_dead(self):
        h = Harness()
        h.herdr.workspace_lists_ok = 1  # the tab map reads, the restore's own listing fails
        h.deck.restore(0)
        self.assertTrue(h.deck.lost)
        self.assertTrue(any(line.startswith("cannot restore yet") for line in h.logs))
        h.herdr.workspace_lists_ok = None
        h.deck.follow(1)
        self.assertEqual(h.deck.harness_pane.keys(), {"ui"})

    def test_nothing_running_before_or_now_arms_wait_after_the_settle(self):
        h = Harness()
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        harness = harness_of(h)
        h.deck.follow(RESTORE_SETTLE_S - 1)
        self.assertEqual(h.herdr.runs(harness), [])
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(harness), ["moveto ui --wait"])

    def test_what_ran_before_and_died_is_resumed_and_what_still_runs_gets_a_plain_shell(self):
        for live, expected in (((), "moveto ui --resume"), (("working",), "moveto ui")):
            h = Harness(befores={"ui": Before(running=True)})
            h.records["ui"] = record("ui", *live)
            h.deck.restore(0)
            h.deck.follow(RESTORE_SETTLE_S)
            self.assertEqual(h.herdr.runs(harness_of(h)), [expected], live)

    def test_under_an_automatic_boot_what_ran_before_waits_for_the_boot(self):
        # fleet-deck start --auto activates in tier order and pace; the restore
        # must not resume every such session at once.
        h = Harness(befores={"ui": Before(running=True)})
        h.deck.booting = lambda: True
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(harness_of(h)), ["moveto ui --wait"])

    def test_during_a_boot_an_outage_in_the_restore_still_waits(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.deck.booting = lambda: True
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(1)
        h.herdr.down = True             # one poll's outage before the decision
        h.deck.follow(2)
        h.herdr.down = False
        for t in range(3, 3 + 2 * RESTORE_SETTLE_S + PANE_MAP_REFRESH_S):
            h.deck.follow(t)
        runs = h.herdr.runs()
        self.assertNotIn("moveto ui --resume", runs)
        self.assertIn("moveto ui --wait", runs)

    def test_with_no_fresh_record_it_waits_then_arms_wait_never_resume(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.records["ui"] = record("ui", age_s=3600)
        h.deck.restore(0)
        harness = harness_of(h)
        h.deck.follow(RESTORE_WAIT_S - 1)
        self.assertEqual(h.herdr.runs(harness), [])
        h.deck.follow(RESTORE_WAIT_S)
        self.assertEqual(h.herdr.runs(harness), ["moveto ui --wait"])

    def test_a_pane_a_person_started_something_in_during_the_wait_is_not_armed(self):
        h = Harness()
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        harness = harness_of(h)
        h.herdr.proc[harness] = in_moveto("ui")
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(harness), [])

    def test_a_milestone_one_tab_is_adopted_as_the_harness(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", None, BARE)])
        h = Harness(herdr)
        h.deck.restore(0)
        self.assertEqual(herdr.panes["p0"]["label"], "harness")
        self.assertEqual(sorted(p["label"] for p in herdr.panes.values()), ["agent", "harness", "shell", "status"])
        self.assertFalse(any(c[:2] == ("tab", "create") for c in herdr.calls))

    def test_a_tab_from_before_the_agent_pane_gets_one_below_its_status(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", four_panes("ui", "p")[:3])
        h = Harness(herdr)
        h.harness_runs("p0")
        h.records["ui"] = record("ui", "working")
        h.deck.restore(0)
        split = next(c for c in herdr.calls if c[:2] == ("pane", "split"))
        self.assertEqual((split[2], split[4]), ("p2", "down"))
        agent = next(p for p, pane in herdr.panes.items() if pane["label"] == "agent")
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(herdr.runs(), [VIEW], "the agent's screen, and no moveto")
        self.assertEqual(herdr.runs(agent), [VIEW])
        self.assertIs(h.deck.tracks["ui"].state, State.RUNNING, "the harness is followed as before")

    def test_an_overlay_from_before_the_agent_pane_is_not_taken_for_it(self):
        # FleetDeck before this change titled the overlay "agent".
        overlay = {"shell_pid": 70, "foreground_process_group_id": 70, "foreground_processes": [
            {"pid": 70, "argv": BOARD["foreground_processes"][0]["argv"][:-1] + ["agent"]}]}
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", overlay)])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        self.assertEqual(herdr.panes["p3"]["label"], "this agent")
        agent = [p for p, pane in herdr.panes.items() if pane["label"] == "agent"]
        self.assertEqual(len(agent), 1)
        self.assertNotEqual(agent[0], "p3")
        h.deck.follow(1)
        self.assertEqual(herdr.runs(agent[0]), [VIEW])
        self.assertEqual(herdr.runs("p3"), [], "the overlay is left as it is")

    def test_an_agent_pane_already_showing_the_agent_is_left_as_it_is(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", four_panes("ui", "p"))
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(1)
        self.assertEqual(h.deck.waiting, {})
        self.assertEqual(herdr.runs("p3"), [])
        self.assertFalse(any(c[:2] == ("pane", "split") for c in herdr.calls))

    def test_an_agent_pane_held_by_anything_else_waits_for_its_prompt(self):
        for held in (BUSY, in_view("other"), in_moveto("ui")):
            herdr = FakeHerdr()
            herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", held)])
            h = Harness(herdr)
            h.records["ui"] = record("ui")
            h.deck.restore(0)
            for at in range(1, RESTORE_WAIT_S + 10, 2):
                h.deck.follow(at)
            self.assertEqual(herdr.runs("p3"), [], "nothing typed into what runs there")
            self.assertEqual(sum("still busy" in line for line in h.logs), 1, "said once")
            herdr.proc["p3"] = BARE
            h.deck.follow(RESTORE_WAIT_S + 12)
            self.assertEqual(herdr.runs("p3"), [VIEW])

    def test_an_agent_pane_restored_focused_is_told_nothing(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", BARE)])
        herdr.panes["p3"]["focused"] = True
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        real_run = herdr.call

        def call(*args):
            out = real_run(*args)
            if args[:3] == ("pane", "run", "p3"):   # the view comes up, and holds the pane
                import fabric_deck
                herdr.panes["p3"]["terminal_title"] = fabric_deck.view_title("ui", MARK)
                herdr.proc["p3"] = in_view("ui")
            return out

        herdr.call = call
        h.deck.restore(0)
        h.deck.follow(1)
        (typed,) = herdr.runs("p3")
        self.assertEqual(typed, VIEW, "marked, as every start")
        self.assertEqual([c for c in herdr.calls if c[:2] == ("pane", "send-text")], [],
                         "the list's focus is the server's default target, perhaps no one's")

    def test_a_queued_restart_is_cancelled_when_the_pane_takes_another_role(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", four_panes("ui", "p"))
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(PANE_MAP_REFRESH_S + 1)
        import fabric_deck
        queued = ("ui", "p3", fabric_deck.VIEW)  # the mode, not the typed command VIEW
        herdr.proc["p3"] = BUSY  # it ended, and its shell is not at its prompt yet
        h.deck.waiting[queued] = PANE_MAP_REFRESH_S + 1
        herdr.panes["p3"]["label"] = "status"  # the person gave the pane another role
        herdr.proc["p3"] = BARE
        for at in range(2, 6):
            h.deck.follow(at * PANE_MAP_REFRESH_S + at)
        self.assertEqual(herdr.runs("p3"), [], "nothing typed into a pane the deck no longer owns")
        self.assertNotIn(queued, h.deck.waiting)

    def test_a_busy_restore_start_is_cancelled_when_the_pane_takes_another_role(self):
        for role in ("status", "harness"):
            herdr = FakeHerdr()
            herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", BUSY)])
            h = Harness(herdr)
            h.records["ui"] = record("ui")
            h.deck.restore(0)
            h.deck.follow(1)
            self.assertEqual(herdr.runs("p3"), [], f"{role}: busy, not typed yet")
            herdr.panes["p3"]["label"] = role
            herdr.proc["p3"] = BARE
            for at in range(1, 5):
                h.deck.follow(at * PANE_MAP_REFRESH_S + at)
            self.assertEqual(herdr.runs("p3"), [], f"{role}: the agent screen is never typed there")
            if role == "harness":
                # Two harness labels: the account is forgotten (or the pane
                # unlisted) before the agent-pane guard is reached.
                self.assertNotIn(("ui", "p3", fabric_deck_mode_view()), h.deck.waiting)
                # p3 listed after p0: the tab's harness is p3 now, so the
                # account is forgotten (the guard against typing into a harness).
                self.assertNotIn("ui", h.deck.harness_pane)

    def test_a_busy_pane_given_another_role_loses_its_queued_start(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", BUSY)])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(1)
        herdr.panes["p3"]["label"] = "status"  # and it stays busy
        for at in range(1, 5):
            h.deck.follow(at * PANE_MAP_REFRESH_S + at + RESTORE_WAIT_S)
        self.assertNotIn(("ui", "p3", fabric_deck_mode_view()), h.deck.waiting)
        self.assertFalse(any("p3 is still busy" in line for line in h.logs), "not its agent pane any more")
        self.assertEqual(sum("no longer its agent pane" in line for line in h.logs), 1)

    def test_a_pane_relabelled_since_the_last_map_read_is_not_typed_into(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", BUSY)])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(1)
        herdr.panes["p3"]["label"] = "status"  # no map read since
        herdr.proc["p3"] = BARE
        h.deck.follow(2)
        self.assertEqual(herdr.runs("p3"), [], "the label is read again before typing")
        self.assertNotIn("ui", h.deck.agent_pane)
        self.assertEqual(sum("no longer its agent pane" in line for line in h.logs), 1)

    def test_an_ended_screen_restarted_after_the_last_client_left_is_told_nothing(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", four_panes("ui", "p"))
        herdr.panes["p3"]["focused"] = True  # the person was on agent, then detached
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        real_run = herdr.call

        def call(*args):
            out = real_run(*args)
            if args[:3] == ("pane", "run", "p3"):
                import fabric_deck
                herdr.panes["p3"]["terminal_title"] = fabric_deck.view_title("ui", MARK)
                herdr.proc["p3"] = in_view("ui")
            return out

        herdr.call = call
        h.deck.restore(0)
        h.deck.follow(PANE_MAP_REFRESH_S + 1)
        herdr.proc["p3"] = BARE  # the screen crashed
        for at in range(2, 5):
            h.deck.follow(at * PANE_MAP_REFRESH_S + at)
        self.assertEqual(herdr.runs("p3"), [VIEW], "started again")
        self.assertEqual([c for c in herdr.calls if c[:2] == ("pane", "send-text")], [])

    def test_a_view_started_out_of_sight_is_never_told_an_inferred_focus(self):
        # The person picks the agent while its screen starts, then may leave
        # (the last client detaching): the pane list still reads it focused,
        # as the server's default target. The deck tells it nothing; the
        # screen fetches at its first key, never while nobody watches.
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", BARE)])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        real = herdr.call

        def call(*args):
            out = real(*args)
            if args[:3] == ("pane", "run", "p3"):
                herdr.proc["p3"] = in_view("ui")
            return out

        herdr.call = call
        h.deck.restore(0)
        h.deck.follow(1)
        self.assertEqual(herdr.runs("p3"), [VIEW])
        import fabric_deck
        herdr.panes["p3"].update(terminal_title=fabric_deck.view_title("ui", MARK), focused=True)
        for at in range(2, 8):
            h.deck.follow(at * PANE_MAP_REFRESH_S + at)
        self.assertEqual([c for c in herdr.calls if c[:2] == ("pane", "send-text")], [])

    def test_an_ended_agent_screen_is_started_again_once_per_end(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", four_panes("ui", "p"))
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(PANE_MAP_REFRESH_S + 1)
        self.assertEqual(herdr.runs("p3"), [], "its screen runs")
        herdr.proc["p3"] = BARE  # it crashed; a start that fails leaves it bare
        h.deck.follow(2 * PANE_MAP_REFRESH_S + 2)
        h.deck.follow(2 * PANE_MAP_REFRESH_S + 3)
        self.assertEqual(herdr.runs("p3"), [VIEW])
        h.deck.follow(3 * PANE_MAP_REFRESH_S + 4)
        h.deck.follow(4 * PANE_MAP_REFRESH_S + 5)
        self.assertEqual(herdr.runs("p3"), [VIEW], "not typed again until seen running again")

    def test_a_forgotten_account_gets_no_agent_screen_started_again(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", four_panes("ui", "p"))
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(PANE_MAP_REFRESH_S + 1)
        herdr.panes["p0"]["label"] = "mine"  # the person took the harness pane over
        h.deck.follow(2 * PANE_MAP_REFRESH_S + 2)
        self.assertNotIn("ui", h.deck.harness_pane, "forgotten")
        self.assertNotIn("ui", h.deck.agent_pane)
        herdr.proc["p3"] = BARE
        for at in range(3, 7):
            h.deck.follow(at * PANE_MAP_REFRESH_S + at)
        self.assertEqual(herdr.runs("p3"), [], "nothing typed into a tab no longer followed")

    def test_an_agent_pane_a_person_took_over_or_closed_is_the_decks_no_more(self):
        for change in ("relabel", "close"):
            herdr = FakeHerdr()
            herdr.add_tab("ui", four_panes("ui", "p"))
            h = Harness(herdr)
            h.records["ui"] = record("ui")
            h.deck.restore(0)
            h.deck.follow(PANE_MAP_REFRESH_S + 1)
            if change == "relabel":
                herdr.panes["p3"]["label"] = "mine"
                herdr.proc["p3"] = BARE
            else:
                del herdr.panes["p3"]
            for at in range(2, 6):
                h.deck.follow(at * PANE_MAP_REFRESH_S + at)
            self.assertEqual(herdr.runs("p3"), [], change)
            self.assertNotIn("ui", h.deck.agent_pane, change)
            self.assertIn("ui", h.deck.harness_pane, f"{change}: the account is still followed")
            looks = [c for c in herdr.calls if c[:2] == ("pane", "process-info") and c[-1] == "p3"]
            self.assertLessEqual(len(looks), 2, f"{change}: not looked at every map read")

    def test_a_view_a_toggle_started_meanwhile_is_not_typed_again(self):
        # The pane was bare at the deck's first look; under the lock, a toggle
        # has already typed the view there.
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", BARE)])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        looks = []
        real = herdr.process_info

        def process_info(pane):
            if pane == "p3":
                looks.append(1)
                if len(looks) == 2:
                    herdr.proc["p3"] = in_view("ui")
            return real(pane)

        herdr.process_info = process_info
        h.deck.restore(0)
        h.deck.follow(1)
        self.assertEqual(herdr.runs("p3"), [])
        h.deck.follow(3)
        self.assertNotIn(("ui", "p3", "view"), h.deck.waiting, "found running at the next look")

    def test_the_deck_types_a_view_only_under_the_lock_a_toggle_takes(self):
        import contextlib
        import fabric_deck
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", BARE)])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        held = []

        @contextlib.contextmanager
        def lock(directory=None):
            held.append(directory)
            yield
            held.append("released")

        real_lock, real_run = fabric_deck.view_lock, herdr.call

        def call(*args):
            if args[:2] == ("pane", "run") and args[2] == "p3":
                self.assertEqual(held[-1:], [LOCK_DIR.name], "typed while the lock is held")
            return real_run(*args)

        fabric_deck.view_lock, herdr.call = lock, call
        try:
            h.deck.restore(0)
            h.deck.follow(1)
        finally:
            fabric_deck.view_lock = real_lock
        self.assertEqual(herdr.runs("p3"), [VIEW])
        self.assertEqual(held, [LOCK_DIR.name, "released"])

    def test_a_focused_start_left_while_starting_is_told_once_it_can_hear(self):
        import fabric_deck
        for still_there, told in ((True, [("pane", "send-text", "p3", "\x1b[I")]),
                                  (False, [("pane", "send-text", "p3", "\x1b[O")])):
            herdr = FakeHerdr()
            herdr.add_tab("ui", [("p3", "agent", BARE)])
            herdr.panes["p3"]["focused"] = True
            looks = []

            def sleep(_):
                looks.append(1)
                if len(looks) == 2:   # the view sets its title; the person may have gone
                    herdr.panes["p3"].update(terminal_title=fabric_deck.view_title("ui", MARK),
                                             focused=still_there)
                    herdr.proc["p3"] = in_view("ui")

            fabric_deck.start_view(herdr, "p3", "ui", True, sleep)
            sent = [c for c in herdr.calls if c[:2] == ("pane", "send-text")]
            self.assertEqual(sent, told, still_there)

    def test_a_move_between_the_read_and_the_send_is_told_again(self):
        import fabric_deck
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p3", "agent", in_view("ui"))])
        herdr.panes["p3"].update(focused=True)
        real = herdr.call

        def call(*args):
            out = real(*args)
            if args[:2] == ("pane", "send-text") and len([c for c in herdr.calls if c[:2] == args[:2]]) == 1:
                herdr.panes["p3"]["focused"] = False   # the person moved just as it was sent
            return out

        herdr.call = call
        fabric_deck.tell_focus(herdr, "p3", "ui")
        self.assertEqual([c[3] for c in herdr.calls if c[:2] == ("pane", "send-text")], ["\x1b[I", "\x1b[O"])

    def test_focus_that_never_settles_is_left_unfocused(self):
        # The person moves within every round trip: the last report is not
        # verified, and a focused one could keep a hidden view fetching.
        import fabric_deck
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p3", "agent", in_view("ui"))])
        herdr.panes["p3"]["focused"] = True
        real = herdr.call

        def call(*args):
            out = real(*args)
            if args[:2] == ("pane", "send-text"):
                herdr.panes["p3"]["focused"] = not herdr.panes["p3"]["focused"]
            return out

        herdr.call = call
        fabric_deck.tell_focus(herdr, "p3", "ui")
        sent = [c[3] for c in herdr.calls if c[:2] == ("pane", "send-text")]
        self.assertEqual(sent[-1], "\x1b[O")
        self.assertEqual(len(sent), fabric_deck.FOCUS_READS + 1)

    def test_the_last_unfocusing_report_too_reaches_only_the_view(self):
        import fabric_deck
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p3", "agent", in_view("ui"))])
        herdr.panes["p3"]["focused"] = True
        real = herdr.call

        def call(*args):
            out = real(*args)
            if args[:2] == ("pane", "send-text"):
                herdr.panes["p3"]["focused"] = not herdr.panes["p3"]["focused"]
                if len([c for c in herdr.calls if c[:2] == args[:2]]) == fabric_deck.FOCUS_READS:
                    herdr.proc["p3"] = BARE   # the view ends just then
            return out

        herdr.call = call
        fabric_deck.tell_focus(herdr, "p3", "ui")
        sent = [c for c in herdr.calls if c[:2] == ("pane", "send-text")]
        self.assertEqual(len(sent), fabric_deck.FOCUS_READS, "nothing more into the shell")

    def test_a_login_with_a_trailing_newline_is_no_login(self):
        from fabric_deck import SAFE_LOGIN
        self.assertTrue(SAFE_LOGIN.match("ui"))
        for label in ("ui\n", "ui\nrm", "ui x", "Ui"):
            self.assertIsNone(SAFE_LOGIN.match(label), repr(label))

    def test_a_shell_running_a_script_is_no_prompt_to_type_at(self):
        from fabric_deck import at_bare_shell

        def shell(*argv):
            return {"shell_pid": 10, "foreground_process_group_id": 10,
                    "foreground_processes": [{"pid": 10, "argv": list(argv)}]}

        # (`--rcfile <file>` reads as busy: its value is not an option. Safe,
        # and herdr starts a pane's shell with no arguments.)
        for argv in (["bash"], ["/bin/bash"], ["-bash"], ["bash", "-l"], ["zsh", "-i"], ["bash", "--norc"]):
            self.assertTrue(at_bare_shell(shell(*argv)), argv)
        for argv in (["bash", "-c", "read -r answer"], ["bash", "-lc", "read"], ["bash", "x.sh"], ["bash", "-c", "-x"],
                     ["sh", "/usr/bin/script", "arg"], ["vim"], ["fish", "--command=read"],
                     ["fish", "-C", "read"], ["bash", "--rcfile", "x"], ["bash", "--", "-x"]):
            self.assertFalse(at_bare_shell(shell(*argv)), argv)

    def test_an_agent_pane_running_a_script_is_never_typed_into(self):
        script = {"shell_pid": 10, "foreground_process_group_id": 10,
                  "foreground_processes": [{"pid": 10, "argv": ["bash", "-c", "read -r answer"]}]}
        herdr = FakeHerdr()
        herdr.add_tab("ui", [*four_panes("ui", "p")[:3], ("p3", "agent", script)])
        h = Harness(herdr)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        for at in range(1, 9, 2):
            h.deck.follow(at)
        self.assertEqual(herdr.runs("p3"), [])

    def test_only_fabric_views_own_steps_are_taken_for_it(self):
        import fabric_deck
        script = "/x/fleet-deck/fabric-view"
        for argv in (["env", "FABRIC_VIEW_START=m", script, "agent"], ["bash", script, "agent"],
                     ["/usr/local/bin/fabric-python", "-B", "-c", "from fabric_view import main", "/x", "agent"]):
            self.assertTrue(fabric_deck.is_overlay_view(argv), argv)
        for argv in (["vim", script, "agent"], ["less", script, "agent"]):
            self.assertFalse(fabric_deck.is_overlay_view(argv), argv)
        # Whatever AGENT_FABRIC_PYTHON is called, the launcher's code names the view.
        self.assertTrue(fabric_deck.is_overlay_view(["/opt/pypy3", "-B", "-c", "from fabric_view import main", "/x",
                                                     "agent"]))

    def test_no_report_reaches_a_pane_the_view_has_left(self):
        import fabric_deck
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p3", "agent", BARE)])
        herdr.panes["p3"]["focused"] = True
        fabric_deck.tell_focus(herdr, "p3", "ui")
        self.assertEqual([c for c in herdr.calls if c[:2] == ("pane", "send-text")], [], "never into a shell")

    def test_a_view_that_never_reports_ready_is_told_nothing(self):
        # It holds its focus unknown: it fetches at a key or a real report,
        # never on a snapshot that may be stale by the time it can hear.
        import fabric_deck
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p3", "agent", BARE)])
        herdr.panes["p3"]["focused"] = True
        fabric_deck.start_view(herdr, "p3", "ui", True, lambda _: None)
        self.assertEqual([c for c in herdr.calls if c[:2] == ("pane", "send-text")], [])

    def test_an_overlay_is_known_by_what_runs_in_it(self):
        import fabric_deck
        argv = BOARD["foreground_processes"][0]["argv"][:-1] + ["agent"]
        self.assertTrue(fabric_deck.is_overlay_view(argv))
        self.assertFalse(fabric_deck.is_overlay_view(argv[:-1] + ["board"]))
        self.assertFalse(fabric_deck.is_overlay_view(in_view("ui")["foreground_processes"][0]["argv"]))
        self.assertFalse(fabric_deck.is_overlay_view(["vim", "agent"]))

    def test_an_unfocused_start_holds_on_until_the_shell_hands_on(self):
        import fabric_deck
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p3", "agent", BARE)])
        looks = []

        def sleep(_):
            looks.append(1)
            if len(looks) == 3:
                herdr.proc["p3"] = in_view("ui")

        fabric_deck.start_view(herdr, "p3", "ui", False, sleep)
        self.assertEqual(len(looks), 3, "until the view holds the foreground, and no longer")

    def test_a_run_that_fails_is_tried_again_at_the_pane_as_it_is_then(self):
        for pane, typed in (("p3", VIEW), ("p1", "moveto ui")):
            herdr = FakeHerdr()
            herdr.add_tab("ui", [("p0", "harness", in_moveto("ui", WAIT)), ("p1", "shell", BARE),
                                 ("p2", "status", in_moveto("ui", WATCH)), ("p3", "agent", BARE)])
            h = Harness(herdr)
            h.records["ui"] = record("ui")
            herdr.fail_once = {("run", pane)}
            h.deck.restore(0)
            for at in range(1, PANE_MAP_REFRESH_S + 4, 2):
                h.deck.follow(at)
            self.assertFalse(herdr.fail_once, f"{pane}'s run failed once")
            # The fake records the failed call too: one refused, one retry.
            self.assertEqual(herdr.runs(pane), [typed, typed], f"{pane}: typed again, once")

    def test_a_views_mark_is_read_from_its_environment(self):
        import fabric_deck
        with tempfile.TemporaryDirectory() as proc:
            os.makedirs(os.path.join(proc, "40"))
            with open(os.path.join(proc, "40", "environ"), "wb") as f:
                f.write(b"HOME=/h\0FABRIC_VIEW_START=m7\0TERM=x\0")
            os.makedirs(os.path.join(proc, "41"))
            with open(os.path.join(proc, "41", "environ"), "wb") as f:
                f.write(b"HOME=/h\0")
            self.assertEqual(fabric_deck.view_mark(40, proc), "m7")
            self.assertIsNone(fabric_deck.view_mark(41, proc))
            self.assertIsNone(fabric_deck.view_mark(42, proc), "gone")

    def test_the_view_is_typed_as_one_safe_word_per_argument(self):
        import fabric_deck
        real = fabric_deck.BOARD_DIR
        fabric_deck.BOARD_DIR = "/home/o p/fleet-deck"   # a checkout path with a space
        try:
            typed = agent_view_command("ui")
        finally:
            fabric_deck.BOARD_DIR = real
        self.assertEqual(shlex.split(typed), ["/home/o p/fleet-deck/fabric-view", "agent", "--agent", "ui", "--in-tab"])
        self.assertTrue(is_agent_view(in_view("ui")["foreground_processes"][0]["argv"], "ui"))
        self.assertFalse(is_agent_view(in_view("ui")["foreground_processes"][0]["argv"], "u"))
        self.assertFalse(is_agent_view(["vim", "agent", "--agent", "ui", "--in-tab"], "ui"))

    def test_the_agent_label_is_a_role_of_the_tab(self):
        tab = read_tab("ui", "t", "w", [PaneInfo("a", "t", "harness"), PaneInfo("b", "t", "agent")])
        self.assertEqual(tab.panes, {"harness": "a", "agent": "b"})

    def test_a_tab_split_by_hand_is_left_alone_and_said_once(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", None, BARE), ("p1", None, BARE)])
        h = Harness(herdr)
        h.deck.restore(0)
        h.deck.restore(1)
        self.assertEqual(h.herdr.runs(), [])
        self.assertFalse(any(c[1] in ("split", "rename") for c in herdr.calls))
        self.assertEqual(sum("split by hand" in line for line in h.logs), 1)

    def test_a_surviving_harness_is_classified_and_never_rearmed(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", "harness", BARE), ("p1", "shell", in_moveto("ui")),
                             ("p2", "status", in_moveto("ui", WATCH)), ("p3", "agent", in_view("ui"))])
        h = Harness(herdr)
        h.harness_runs("p0")
        h.records["ui"] = record("ui", "working")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(), [], "nothing is typed while moveto runs")
        self.assertEqual(h.herdr.reports("p0")[1][-1], "working", "after the account")

    def test_an_ssh_pane_whose_own_connection_carries_the_live_session_is_running(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", "harness", in_ssh("ui", WAIT)), ("p1", "shell", in_ssh("ui", "shell", pid=21)),
                             ("p2", "status", in_ssh("ui", WATCH, pid=22)), ("p3", "agent", in_view("ui"))])
        h = Harness(herdr)
        h.sockets[20] = frozenset({endpoint(*PANE_END)})
        # sshd's view through a dual-stack socket: the mapped form.
        h.records["ui"] = ssh_record("ui", ("working", ("::ffff:127.0.0.1", 40001)))
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(), [])
        self.assertEqual(h.herdr.reports("p0")[1][-1], "working")

    def test_an_ssh_pane_whose_connection_carries_no_live_session_reads_running_elsewhere(self):
        for other in (("idle", ("127.0.0.1", 40002)), ("idle", ("10.0.0.5", 40001)), ("working", None)):
            herdr = FakeHerdr()
            herdr.add_tab("ui", [("p0", "harness", in_ssh("ui", WAIT)), ("p1", "shell", in_ssh("ui", "shell", pid=21)),
                                 ("p2", "status", in_ssh("ui", WATCH, pid=22)), ("p3", "agent", in_view("ui"))])
            h = Harness(herdr)
            h.sockets[20] = frozenset({endpoint(*PANE_END)})
            # The pane's own end on a session that is over is not a live one.
            h.records["ui"] = ssh_record("ui", other, ("gone", PANE_END))
            h.deck.restore(0)
            h.deck.follow(RESTORE_SETTLE_S)
            self.assertEqual(h.herdr.runs(), [], other)
            self.assertEqual(h.herdr.reports("p0")[-1][-1], "unknown=running elsewhere", other)

    def test_a_session_started_elsewhere_while_an_ssh_pane_waits_reads_running_elsewhere(self):
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", "harness", in_ssh("ui", WAIT)), ("p1", "shell", in_ssh("ui", "shell", pid=21)),
                             ("p2", "status", in_ssh("ui", WATCH, pid=22)), ("p3", "agent", in_view("ui"))])
        h = Harness(herdr)
        h.sockets[20] = frozenset({endpoint(*PANE_END)})
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertIn("idle=dormant", h.herdr.reports("p0")[-1])
        h.records["ui"] = ssh_record("ui", ("working", ("127.0.0.1", 50123)))
        h.deck.follow(RESTORE_SETTLE_S + 1)
        h.deck.follow(RESTORE_SETTLE_S + 1 + SAME_SESSION_S)
        self.assertEqual(h.herdr.reports("p0")[-1][-1], "unknown=running elsewhere")
        self.assertEqual(h.herdr.runs(), [], "nothing is typed while ssh runs the account")

    def test_an_ssh_pane_with_no_endpoint_read_takes_the_accounts_session_as_its_own(self):
        # A ProxyJump ssh, a ControlMaster client, or one read mid-connect: no
        # socket of its own links the pane to a session, so the old rule holds.
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", "harness", in_ssh("ui", WAIT)), ("p1", "shell", in_ssh("ui", "shell")),
                             ("p2", "status", in_ssh("ui", WATCH)), ("p3", "agent", in_view("ui"))])
        h = Harness(herdr)
        h.records["ui"] = record("ui", "working")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(), [], "nothing is typed while ssh runs the account")
        self.assertEqual(h.herdr.reports("p0")[1][-1], "working", "after the account")
        h.records["ui"] = record("ui", "none")
        h.deck.follow(RESTORE_SETTLE_S + 30)
        self.assertEqual(h.herdr.runs(), [])
        self.assertIn("idle=shell", h.herdr.reports("p0")[-1])

    def test_the_sole_ssh_pane_of_an_account_none_of_whose_sessions_is_linked_carries_its_one_session(self):
        # Its ssh connected before enter-ssh recorded ssh_client, and the deck
        # that kept the link in memory restarted since.
        herdr = FakeHerdr()
        herdr.add_tab("ui", [("p0", "harness", in_ssh("ui", WAIT)), ("p1", "shell", in_ssh("ui", "shell", pid=21)),
                             ("p2", "status", in_ssh("ui", WATCH, pid=22)), ("p3", "agent", in_view("ui"))])
        h = Harness(herdr)
        h.sockets[20] = frozenset({endpoint(*PANE_END)})
        h.records["ui"] = ssh_record("ui", ("working", None), ("gone", None))
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        self.assertEqual(h.herdr.runs(), [])
        self.assertEqual(h.herdr.reports("p0")[1][-1], "working", "after the account")
        self.assertEqual(h.deck.tracks["ui"].state, State.RUNNING)

    def test_an_unlinked_session_is_not_guessed_for_a_pane_with_a_rival(self):
        # Two live sessions, a second tab of the login, or a link anywhere in
        # the record: the link decides, and none is found for this pane.
        cases = (("two live", (("working", None), ("idle", None)), False),
                 ("second tab", (("working", None),), True),
                 ("linked elsewhere", (("working", None), ("idle", ("10.0.0.5", 40001))), False),
                 ("linked and over", (("working", None), ("gone", ("10.0.0.5", 40001))), False))
        for name, sessions, second_tab in cases:
            herdr = FakeHerdr()
            herdr.add_tab("ui", [("p0", "harness", in_ssh("ui", WAIT)), ("p1", "shell", in_ssh("ui", "shell", pid=21)),
                                 ("p2", "status", in_ssh("ui", WATCH, pid=22)), ("p3", "agent", in_view("ui"))])
            if second_tab:
                herdr.add_tab("ui", [("q0", "harness", in_ssh("ui", WAIT, pid=30))])
            h = Harness(herdr)
            h.sockets[20] = frozenset({endpoint(*PANE_END)})
            h.records["ui"] = ssh_record("ui", *sessions)
            h.deck.restore(0)
            h.deck.follow(RESTORE_SETTLE_S)
            self.assertEqual(h.herdr.runs(), [], name)
            self.assertEqual(h.herdr.reports("p0")[-1][-1], "unknown=running elsewhere", name)
            self.assertEqual(h.deck.tracks["ui"].state, State.ELSEWHERE, name)
            self.assertEqual(h.herdr.reports("q0"), [], name)

    def test_an_ssh_pane_with_a_stale_record_is_left_as_it_was(self):
        # With and without the pane's own end read, the record carrying it or not.
        for sockets, stale in ((None, record("ui", "working", age_s=10_000)),
                               (frozenset({endpoint(*PANE_END)}), ssh_record("ui", ("working", PANE_END), age_s=10_000)),
                               (frozenset({endpoint(*PANE_END)}), None)):
            herdr = FakeHerdr()
            herdr.add_tab("ui", [("p0", "harness", in_ssh("ui", WAIT)), ("p1", "shell", in_ssh("ui", "shell")),
                                 ("p2", "status", in_ssh("ui", WATCH)), ("p3", "agent", in_view("ui"))])
            h = Harness(herdr)
            if sockets is not None:
                h.sockets[20] = sockets
            if stale is not None:
                h.records["ui"] = stale
            h.deck.restore(0)
            h.deck.follow(RESTORE_SETTLE_S)
            self.assertEqual(h.herdr.runs(), [], stale)
            self.assertFalse(any("working" in r[-1] or "elsewhere" in r[-1] for r in h.herdr.reports("p0")), stale)
            # The panel shows a stale record as stale whatever the state: the state itself is unclassified.
            self.assertNotIn(getattr(h.deck.tracks.get("ui"), "state", None), (State.RUNNING, State.ELSEWHERE), stale)

    def test_an_account_with_an_unsafe_login_is_never_typed(self):
        h = Harness(logins=("ui; rm -rf ~",))
        h.deck.restore(0)
        h.deck.follow(RESTORE_WAIT_S)
        self.assertEqual(h.herdr.runs(), [])
        self.assertFalse(any(c[:2] == ("tab", "create") for c in h.herdr.calls))


class Follow(unittest.TestCase):
    def ready(self, befores=None):
        """A restored account whose harness pane runs `moveto ui --wait`."""
        h = Harness(befores=befores)
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        harness = harness_of(h)
        h.herdr.proc[harness] = in_moveto("ui", WAIT)
        h.deck.follow(RESTORE_SETTLE_S + 1)
        return h, harness

    def test_dormant_then_enter_shows_the_session_and_records_running(self):
        h, harness = self.ready()
        self.assertEqual(h.herdr.reports(harness)[-1][-3:], ("idle=dormant", "--state-label", "done=dormant"))
        self.assertIn(("--display-agent", "dormant"), list(zip(h.herdr.reports(harness)[-1], h.herdr.reports(harness)[-1][1:])))
        h.harness_runs(harness)
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        self.assertEqual(h.herdr.reports(harness)[-3][-1], "working")
        self.assertEqual(h.store, {"ui": Before(running=True)})

    def test_a_blocked_report_herdr_did_not_apply_is_logged_with_what_herdr_holds(self):
        h, harness = self.ready()
        h.harness_runs(harness)
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        h.herdr.drops_reports.add(harness)
        h.herdr.panes[harness]["agent_session"] = {"source": "herdr:claude", "agent": "claude",
                                                    "kind": "id", "value": "s-1"}
        h.records["ui"] = record("ui", "blocked")
        h.deck.follow(22)
        self.assertEqual(h.herdr.reports(harness)[-3][-1], "blocked", "the deck did report it")
        self.assertIn(f"ui: herdr holds working for pane {harness} after the deck reported blocked "
                      "(agent claude, session herdr:claude/claude)", h.logs)
        self.assertFalse([line for line in h.logs if "s-1" in line], "the session's id stays out")

    def test_a_report_herdr_applied_logs_no_difference_and_an_unread_idle_is_done(self):
        h, harness = self.ready()
        h.harness_runs(harness)
        for at, state in ((20, "working"), (22, "blocked"), (24, "idle")):
            h.records["ui"] = record("ui", state)
            h.deck.follow(at)
        h.herdr.agent_status[harness] = "done"
        h.deck._read_back("ui", harness, Shown("idle", ""))
        self.assertFalse([line for line in h.logs if "herdr holds" in line], h.logs)

    def test_a_pane_that_cannot_be_read_back_is_logged_and_the_deck_goes_on(self):
        h, harness = self.ready()
        h.harness_runs(harness)
        h.herdr.fail_once.add(("get", harness))
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        self.assertEqual(sum(harness in line for line in h.logs[-1:]), 1)
        self.assertIn("could not be read back", h.logs[-1])
        self.assertIsNotNone(h.deck.mapped_at, "not taken as a failure of the account's tab")
        h.herdr.drops_reports.add(harness)
        h.records["ui"] = record("ui", "blocked")
        h.deck.follow(22)
        self.assertEqual(h.herdr.reports(harness)[-3][-1], "blocked", "the next report is sent")
        self.assertIn("herdr holds working", h.logs[-1], "and read back")

    def test_a_label_command_that_fails_after_the_report_still_has_it_read_back(self):
        h, harness = self.ready()
        h.harness_runs(harness)
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        h.herdr.drops_reports.add(harness)
        refused = lambda *args, _call=h.herdr.call: (
            _ for _ in ()).throw(RuntimeError("metadata refused")) \
            if "--clear-state-labels" in args else _call(*args)
        h.herdr.call = refused
        h.records["ui"] = record("ui", "blocked")
        h.deck.follow(22)
        self.assertIn(f"ui: herdr holds working for pane {harness} after the deck reported blocked "
                      "(agent claude, session none)", h.logs)
        self.assertIn("metadata refused", h.logs[-1], "the label's error still reaches the log")

    def test_an_account_command_that_fails_before_the_report_reads_nothing_back(self):
        h, harness = self.ready()
        h.harness_runs(harness)
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        gets = len([c for c in h.herdr.calls if c[:2] == ("pane", "get")])
        h.herdr.call = lambda *args, _call=h.herdr.call: (
            _ for _ in ()).throw(RuntimeError("account refused")) \
            if "--token" in args else _call(*args)
        h.records["ui"] = record("ui", "blocked")
        h.deck.follow(22)
        self.assertEqual(len([c for c in h.herdr.calls if c[:2] == ("pane", "get")]), gets)
        self.assertNotIn(("pane", "report-agent", harness), [c[:3] for c in h.herdr.calls[-3:]])

    def test_a_resend_is_read_back_too(self):
        h, harness = self.ready()
        h.harness_runs(harness)
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        h.herdr.agent_status[harness] = "idle"
        h.herdr.drops_reports.add(harness)
        h.deck.follow(h.at(21 + RESEND_AFTER_S))
        self.assertIn(f"ui: herdr holds idle for pane {harness} after the deck reported working "
                      "(agent claude, session none)", h.logs)

    def test_an_answer_that_is_not_a_pane_is_logged_as_unreadable(self):
        h, harness = self.ready()
        h.harness_runs(harness)
        h.herdr.call = lambda *args, _call=h.herdr.call: (
            {"pane": ["not", "a", "pane"]} if args[:2] == ("pane", "get") else _call(*args))
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        self.assertIn("could not be read back", h.logs[-1])
        self.assertIsNotNone(h.deck.mapped_at)

    def test_a_session_elsewhere_reads_running_elsewhere_and_touches_nothing(self):
        h, harness = self.ready()
        h.records["ui"] = record("ui", "blocked")
        h.deck.follow(20)
        self.assertEqual(h.herdr.reports(harness)[-1][-1], "done=dormant", "not within the same-session window")
        h.deck.follow(20 + SAME_SESSION_S)
        self.assertEqual(h.herdr.reports(harness)[-1][-1], "unknown=running elsewhere")
        self.assertEqual(h.herdr.runs(harness), ["moveto ui --wait"])

    def test_a_wait_that_ends_is_rearmed_wait_and_reads_dormant_not_failed(self):
        h, harness = self.ready()
        h.herdr.proc[harness] = BARE
        h.deck.follow(30)
        self.assertEqual(h.herdr.reports(harness)[-1][-3:], ("idle=dormant", "--state-label", "done=dormant"))
        self.assertEqual(h.herdr.runs(harness), ["moveto ui --wait"] * 2)

    def test_a_resume_that_ends_before_any_harness_is_failed_and_rearmed_wait(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        harness = harness_of(h)
        self.assertEqual(h.herdr.runs(harness), ["moveto ui --resume"])
        h.deck.follow(RESTORE_SETTLE_S * 3 + 20)
        self.assertEqual(h.herdr.reports(harness)[-1][-1], "blocked=failed")
        self.assertEqual(h.herdr.runs(harness), ["moveto ui --resume", "moveto ui --wait"])

    def test_a_moveto_that_keeps_ending_at_once_is_not_typed_again_and_reads_failed(self):
        h, harness = self.ready()
        h.herdr.proc[harness] = BARE
        for at in range(10, 60, 2):
            h.deck.follow(at)
        self.assertEqual(h.herdr.runs(harness), ["moveto ui --wait"] * 2)
        self.assertEqual(h.herdr.reports(harness)[-1][-1], "blocked=failed")
        self.assertEqual(sum("ended at once twice" in line for line in h.logs), 1)
        # A person starts it again, and it fails again: said again.
        h.herdr.proc[harness] = in_moveto("ui", WAIT)
        h.deck.follow(70)
        h.herdr.proc[harness] = BARE
        for at in range(72, 120, 2):
            h.deck.follow(at)
        self.assertEqual(sum("ended at once twice" in line for line in h.logs), 2)

    def test_a_moveto_list_failure_is_not_a_loss_of_herdr(self):
        h = Harness(befores={"ui": Before(running=True)})
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        h.herdr.proc[harness_of(h)] = in_moveto("ui", RESUME)  # the --resume is starting
        h.logins = None  # moveto --list fails from here on
        h.deck.accounts = lambda: (_ for _ in ()).throw(OSError("moveto --list: timed out"))
        h.deck.follow(RESTORE_SETTLE_S + PANE_MAP_REFRESH_S)
        self.assertFalse(h.deck.lost)
        self.assertNotIn("herdr's server answers: restoring", h.logs)
        self.assertEqual(h.herdr.reports(harness_of(h))[-1][-1], "working=restoring")

    def test_only_a_change_is_reported_until_the_resend_interval(self):
        h, harness = self.ready()
        sent = len(h.herdr.reports(harness))
        h.deck.follow(20)
        self.assertEqual(len(h.herdr.reports(harness)), sent)
        h.deck.follow(RESTORE_SETTLE_S + 1 + RESEND_AFTER_S)
        self.assertEqual(len(h.herdr.reports(harness)), sent + 4,
                         "the account, the state, the clear and the label")

    def test_a_pane_left_by_its_account_gives_back_what_the_deck_set(self):
        h, harness = self.ready()
        h.logins = []
        h.deck.follow(RESTORE_SETTLE_S + 1 + PANE_MAP_REFRESH_S)
        given = [c for c in h.herdr.calls if harness in c][-4:]
        self.assertEqual([c[1] for c in given],
                         ["release-agent", "report-metadata", "report-metadata", "report-metadata"])
        self.assertEqual([c[-1] for c in given[1:]],
                         ["--clear-state-labels", "--clear-display-agent", "account"])

    def test_a_harness_held_by_another_command_reads_unknown_not_dormant(self):
        h, harness = self.ready()
        h.herdr.proc[harness] = BUSY
        h.deck.follow(20)
        self.assertEqual(h.herdr.reports(harness)[-1][-2:], ("--display-agent", "unknown"))

    def test_a_harness_pane_closed_by_hand_is_followed_no_more(self):
        h, harness = self.ready()
        del h.herdr.panes[harness]
        h.deck.follow(RESTORE_SETTLE_S + 1 + PANE_MAP_REFRESH_S)
        calls = len(h.herdr.calls)
        h.deck.follow(RESTORE_SETTLE_S + 3 + PANE_MAP_REFRESH_S)
        self.assertFalse(any(harness in c for c in h.herdr.calls[calls:]))

    def test_a_herdr_server_that_comes_back_is_a_restore(self):
        h, harness = self.ready()
        h.herdr.down = True
        h.deck.follow(100)
        self.assertTrue(h.deck.lost)
        logged = len(h.logs)
        h.deck.follow(102)
        self.assertEqual(len(h.logs), logged, "lost, the deck only tries the map again, quietly")
        h.herdr.down = False
        h.herdr.proc[harness] = BARE
        h.deck.follow(100 + PANE_MAP_REFRESH_S)
        self.assertIn("herdr's server answers: restoring", h.logs)
        self.assertEqual(h.deck.pending.keys(), {"ui"})

    def test_one_accounts_herdr_failure_does_not_stop_the_others(self):
        h = Harness(logins=("ui", "vo"))
        h.records.update(ui=record("ui"), vo=record("vo"))
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        del h.herdr.proc[harness_of(h, "ui")]
        vo = harness_of(h, "vo")
        h.herdr.proc[vo] = in_moveto("vo", WAIT)
        h.records["vo"] = record("vo", "idle")
        h.deck.follow(RESTORE_SETTLE_S + 1)
        h.deck.follow(RESTORE_SETTLE_S + 1 + SAME_SESSION_S)
        self.assertEqual(h.herdr.reports(vo)[-1][-1], "unknown=running elsewhere")
        self.assertTrue(any(line.startswith("ui:") for line in h.logs))

    def test_the_record_keeps_only_placed_accounts(self):
        h, harness = self.ready(befores={"gone": Before(running=True)})
        h.harness_runs(harness)
        h.records["ui"] = record("ui", "working")
        h.deck.follow(20)
        self.assertEqual(h.store, {"ui": Before(running=True)})

    def test_another_server_answering_is_herdr_lost_and_a_restore(self):
        h, harness = self.ready()
        h.instance = OTHER
        h.herdr.proc[harness] = BARE
        h.deck.follow(20)
        self.assertIn("herdr's server was restarted", h.logs)
        self.assertIn("herdr's server answers: restoring", h.logs)
        self.assertEqual(h.deck.pending.keys(), {"ui"})


class BeforeFollow(unittest.TestCase):
    def running(self):
        h = Harness()
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(h.at(RESTORE_SETTLE_S))
        h.records["ui"] = record("ui", "working")
        h.deck.follow(h.at(10))
        self.assertEqual(h.store, {"ui": Before(running=True)})
        return h

    def test_a_session_that_ends_while_herdr_stays_up_settles_as_ended(self):
        h = self.running()
        h.records["ui"] = record("ui")
        h.deck.follow(h.at(20))
        self.assertEqual(h.store["ui"].fall_at, h.wall.timestamp())
        h.deck.follow(h.at(20 + SETTLE_S))
        self.assertEqual(h.store, {"ui": Before(running=False)})

    def test_a_stale_record_notes_no_fall(self):
        h = self.running()
        h.records["ui"] = record("ui", age_s=10_000)
        h.deck.follow(h.at(20))
        h.deck.follow(h.at(20 + SETTLE_S))
        self.assertEqual(h.store, {"ui": Before(running=True)}, "a stale record changes nothing")

    def test_a_session_that_ends_with_herdr_stays_recorded_as_running(self):
        h = self.running()
        h.records["ui"] = record("ui")
        h.deck.follow(h.at(20))
        h.herdr.down = True
        h.deck.follow(h.at(22))
        h.deck.follow(h.at(40))
        self.assertEqual(h.store, {"ui": Before(running=True)})

    def test_a_fall_left_pending_settles_at_start_only_on_the_same_server(self):
        fall = Before(running=True, fall_at=NOW.timestamp() - 30, fall_server=SERVER)
        for instance, running in ((SERVER, False), (OTHER, True)):
            h = Harness(befores={"ui": fall})
            h.instance = instance
            h.deck.restore(0)
            self.assertEqual(h.deck.befores["ui"].running, running, instance)
            self.assertEqual(h.store["ui"].fall_at, None, "settled or dropped, and written")


class NotYet(unittest.TestCase):
    def test_modes_moveto_lacks_are_never_armed_and_the_pane_reads_unknown(self):
        h = Harness(modes=frozenset())
        h.records["ui"] = record("ui")
        h.deck.restore(0)
        h.deck.follow(RESTORE_SETTLE_S)
        h.deck.follow(RESTORE_SETTLE_S + 20)
        self.assertEqual(h.herdr.runs(), ["moveto ui", VIEW], "only the plain shell and the agent's screen")
        last = h.herdr.reports(harness_of(h))[-1]
        self.assertEqual(last[-2:], ("--display-agent", "unknown"), "the row does not read claude")
        self.assertEqual(sum("no --wait" in line for line in h.logs), 1)


class Panel(unittest.TestCase):
    def test_the_pane_id_comes_first_and_no_seq_is_sent(self):
        report = report_command("p1", Shown("idle", "dormant"))
        self.assertEqual(report[:3], ("pane", "report-agent", "p1"))
        self.assertNotIn("--seq", report)
        clear, label = label_commands("p1", Shown("idle", "dormant"))
        self.assertEqual(clear[-1], "--clear-state-labels")
        self.assertNotIn("--clear-state-labels", label, "herdr refuses a clear and a set in one call")
        self.assertEqual(label[-6:], ("--display-agent", "dormant", "--state-label", "idle=dormant",
                                      "--state-label", "done=dormant"))
        self.assertEqual(label_commands("p1", Shown("blocked", "failed"))[1][-4:],
                         ("--display-agent", "failed", "--state-label", "blocked=failed"))

    def test_the_account_token_is_set_with_the_state_and_given_back_on_release(self):
        self.assertEqual(account_command("p1", "rust-ui-dev-01")[:3], ("pane", "report-metadata", "p1"))
        self.assertEqual(account_command("p1", "rust-ui-dev-01")[-2:], ("--token", "account=rust-ui-dev-01"))
        self.assertIn(("--clear-token", "account"), [c[-2:] for c in release_commands("p1")])

    def test_a_running_harness_reads_as_herdrs_own_agent_name_and_state(self):
        clear, name = label_commands("p1", Shown("working", ""))
        self.assertEqual((clear[-1], name[-1]), ("--clear-state-labels", "--clear-display-agent"))

    def test_moveto_modes_are_whole_option_tokens_and_resume_needs_wait(self):
        self.assertEqual(modes_in("usage: moveto <account> [--wait|--resume|--watch]"),
                         frozenset({WAIT, RESUME, WATCH}))
        self.assertEqual(modes_in("usage: moveto <account> [--resume] [--waitfor N]"), frozenset())
        self.assertEqual(modes_in("--watch-later --wait-x"), frozenset())


class SocketPath(unittest.TestCase):
    def test_the_session_herdr_reaches_is_the_one_probed(self):
        import subprocess
        from unittest import mock

        listing = ('{"sessions": [{"name": "default", "default": true, "socket_path": "/d.sock"},'
                   ' {"name": "work", "default": false, "socket_path": "/w.sock"}]}')
        ran = mock.Mock(return_value=subprocess.CompletedProcess([], 0, stdout=listing))
        cases = (({"HERDR_SESSION": "work", "HERDR_SOCKET_PATH": "/x.sock"}, "/x.sock"),
                 ({"HERDR_SESSION": "work"}, "/w.sock"), ({"HERDR_SESSION": "default"}, "/d.sock"),
                 ({}, "/d.sock"))
        for env, expected in cases:
            with mock.patch.dict(os.environ, env, clear=False), mock.patch("subprocess.run", ran):
                for name in {"HERDR_SESSION", "HERDR_SOCKET_PATH"} - env.keys():
                    os.environ.pop(name, None)
                self.assertEqual(herdr_socket_path(), expected, env)


class Proc(unittest.TestCase):
    def fake_proc(self, processes):
        root = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, root)
        for pid, (ppid, comm, argv) in processes.items():
            os.makedirs(os.path.join(root, str(pid)))
            with open(os.path.join(root, str(pid), "stat"), "w") as f:
                f.write(f"{pid} ({comm}) S {ppid} {pid} {pid} 0 -1\n")
            with open(os.path.join(root, str(pid), "cmdline"), "wb") as f:
                f.write(b"\0".join(a.encode() for a in argv) + b"\0")
        os.makedirs(os.path.join(root, "self"))
        return root

    def test_a_harness_is_found_under_the_panes_sudo_through_its_own_pty(self):
        root = self.fake_proc({
            20: (10, "sudo", ["sudo", "-u", "ui"]),
            21: (20, "sudo", ["sudo", "-u", "ui"]),
            22: (21, "bash", ["bash", "-i"]),
            23: (22, "fabric-python", ["/usr/local/bin/fabric-python", "-I", "/a/tools/fabric/launch.py"]),
            30: (1, "claude ) (x", ["claude"]),
        })
        parents = proc_parents(root)
        self.assertEqual(parents[30], 1, "a comm with parentheses is read past")
        argv = lambda pid: proc_argv(pid, root)
        self.assertTrue(harness_under(20, parents, argv))
        self.assertFalse(harness_under(21, {21: 20, 22: 21}, lambda pid: ["bash"]))
        self.assertFalse(harness_under(99, parents, argv), "a pid with no children")

    def test_an_ssh_s_endpoints_are_its_own_established_sockets_local_ends(self):
        root = self.fake_proc({20: (10, "ssh", ["ssh"])})
        fd = os.path.join(root, "20", "fd")
        os.makedirs(fd)
        for n, target in enumerate(("/dev/pts/3", "socket:[111]", "socket:[222]", "socket:[333]", "pipe:[9]")):
            os.symlink(target, os.path.join(fd, str(n)))
        self.assertIsNone(proc_ssh_endpoints(20, root), "no net table read: nothing found")

        def word(ip):  # as the kernel prints an address: 32-bit words in host order
            import ipaddress
            raw = ipaddress.ip_address(ip).packed
            return "".join("%08X" % int.from_bytes(raw[i:i + 4], sys.byteorder) for i in range(0, len(raw), 4))

        def row(local, port, state, inode):
            return f"   0: {word(local)}:{port:04X} {word(local)}:0016 {state} 00000000:00000000 00:00000000 00000000  1000 0 {inode} 1 0"

        os.makedirs(os.path.join(root, "20", "net"))
        header = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        with open(os.path.join(root, "20", "net", "tcp"), "w") as f:
            f.write(header + "\n".join([
                row("127.0.0.1", 40001, "01", 111),
                row("127.0.0.1", 40009, "0A", 222),  # a -L listener: not a connection
                row("127.0.0.1", 40010, "01", 999),  # another process's socket
            ]) + "\n")
        with open(os.path.join(root, "20", "net", "tcp6"), "w") as f:
            f.write(header + row("::ffff:192.0.2.7", 50000, "01", 333) + "\n")
        self.assertEqual(proc_ssh_endpoints(20, root),
                         frozenset({endpoint("127.0.0.1", 40001), endpoint("192.0.2.7", 50000)}))
        self.assertIsNone(proc_ssh_endpoints(21, root), "a process gone")

    def test_a_cycle_in_a_racing_tree_does_not_hang(self):
        self.assertFalse(harness_under(1, {2: 3, 3: 2, 4: 1}, lambda pid: []))


class BeforeFile(unittest.TestCase):
    def test_the_record_is_written_owner_only_and_read_back_whole(self):
        root = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, root)
        path = os.path.join(root, "fabric-deck", "before.json")
        self.assertIsNone(load_befores(path), "no file is a first run")
        befores = {"ui": Before(running=True, fall_at=12.5, fall_server=SERVER), "vo": Before()}
        save_befores(path, befores)
        self.assertEqual(load_befores(path), befores)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_an_entry_of_the_wrong_shape_is_read_as_absent(self):
        root = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, root)
        path = os.path.join(root, "before.json")
        with open(path, "w") as f:
            f.write('{"accounts": {"ui": {"running": "yes"}, "vo": {"running": true, "fall_at": 3, '
                    '"fall_server": ["x", 1]}, "wo": 5}}')
        self.assertEqual(load_befores(path), {"vo": Before(running=True)})
        with open(path, "w") as f:
            f.write("[")
        self.assertEqual(load_befores(path), {})


class ServerInstance(unittest.TestCase):
    def test_the_peer_pid_and_its_start_time_name_the_instance(self):
        import socket

        root = tempfile.mkdtemp(dir=f"/run/user/{os.getuid()}" if os.path.isdir(f"/run/user/{os.getuid()}") else None)
        self.addCleanup(__import__("shutil").rmtree, root)
        path = os.path.join(root, "s.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(path)
        listener.listen(1)
        self.assertEqual(server_instance(path), (os.getpid(), start_ticks(os.getpid())))
        self.assertIsNone(server_instance(os.path.join(root, "none.sock")))
        self.assertIsNone(server_instance(None))


class Backoff(unittest.TestCase):
    def test_waits_grow_and_reset_after_a_healthy_stream(self):
        failures, waits = 0, []
        for _ in range(8):
            failures, wait = next_backoff(failures, 0.5)
            waits.append(wait)
        self.assertEqual(waits, [1, 2, 5, 10, 30, 60, 60, 60])
        self.assertEqual(next_backoff(failures, 61), (1, 1))


class StreamLines(unittest.TestCase):
    def test_a_line_that_fails_to_apply_does_not_end_the_stream(self):
        import sys

        seen, logs = [], []
        stream = None

        def on_line(raw):
            seen.append(raw.strip())
            if raw.strip() == "a":
                raise ValueError("bad")
            stream.closing = True

        stream = Stream(on_line=on_line, log=logs.append,
                        command=(sys.executable, "-c", "print('a'); print('b')"))
        stream.run()
        self.assertEqual(seen, ["a", "b"])
        self.assertEqual(logs, ["a state record was skipped: bad"])


class StopChild(unittest.TestCase):
    def stubborn_child(self):
        import subprocess
        import sys

        child = subprocess.Popen(
            [sys.executable, "-c",
             "import signal,sys,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             "print(flush=True); time.sleep(60)"],
            stdout=subprocess.PIPE, text=True,
        )
        child.stdout.readline()  # its SIGTERM handler is in place
        self.addCleanup(child.stdout.close)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        return child

    def stop(self, child, grace=0.5, signal_after=None):
        import signal
        import threading
        import fabric_deck

        saved = fabric_deck.STOP_CHILD_GRACE_S
        fabric_deck.STOP_CHILD_GRACE_S = grace
        timer = None
        if signal_after is not None:
            timer = threading.Timer(signal_after, os.kill, (os.getpid(), signal.SIGINT))
            timer.start()
        try:
            stop_child(child)
        finally:
            fabric_deck.STOP_CHILD_GRACE_S = saved
            if timer is not None:
                timer.join()

    def test_a_child_that_ignores_terminate_is_killed_and_reaped(self):
        import signal

        child = self.stubborn_child()
        before = signal.getsignal(signal.SIGINT)
        self.stop(child, grace=0.2)
        self.assertEqual(child.returncode, -signal.SIGKILL)
        self.assertIs(signal.getsignal(signal.SIGINT), before, "the handlers are given back")

    def test_a_stop_during_the_grace_is_held_until_the_child_is_reaped(self):
        import signal

        child = self.stubborn_child()
        with self.assertRaises(KeyboardInterrupt):
            self.stop(child, grace=0.5, signal_after=0.1)
        self.assertEqual(child.returncode, -signal.SIGKILL, "reaped before the stop is acted on")


class UnknownStateTest(unittest.TestCase):
    def test_a_record_whose_state_is_unknown_is_no_record(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        ts = now.isoformat()
        unreadable = parse_state_line(json.dumps({
            "address": "h/a", "ts": ts, "state": "unknown", "sessions": [],
            "why": "the account cannot read its session state"}))
        idle = parse_state_line(json.dumps({"address": "h/a", "ts": ts, "state": "idle", "sessions": []}))
        self.assertIsNone(live_of(unreadable, now), "an unreadable account says nothing")
        self.assertEqual(live_of(idle, now).count, 0, "a readable one with no session says 0")

    def test_ctls_stale_unknown_row_with_a_session_is_no_record(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        old = (now - datetime.timedelta(minutes=10)).isoformat()
        stale = parse_state_line(json.dumps({
            "address": "h/a", "ts": old, "state": "unknown",
            "sessions": [{"session": "s1", "state": "working", "since": old}]}))
        self.assertIsNone(live_of(stale, now), "not running elsewhere: it may be gone")

    def test_a_row_without_a_state_keeps_its_sessions(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        row = parse_state_line(json.dumps({
            "address": "h/a", "ts": now.isoformat(),
            "sessions": [{"session": "s1", "state": "working", "since": now.isoformat()}]}))
        self.assertEqual(live_of(row, now).count, 1)


if __name__ == "__main__":
    unittest.main()
