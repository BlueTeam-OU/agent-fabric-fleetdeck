"""fleet-deck against the real fabric-deck process, with herdr, fabric-ctl,
moveto and fabric-whoami replaced by stubs on PATH. A stub herdr server is a
real Unix socket listener, so the deck sees a server instance as it would."""

import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import fleet_deck
import fabric_deck
from fabric_deck import hold_lock, lock_holder, lock_path

HERE = os.path.dirname(os.path.realpath(__file__))

STUBS = {
    # The state stream records its pid, then waits to be stopped.
    "fabric-ctl": """
        if [ "$4" = "--follow" ] || [ "$3" = "--follow" ]; then
            echo $$ > "$STUB_DIR/stream.pid"
            exec sleep 3600
        fi
        exit 0
    """,
    "moveto": "exit 0",
    "fabric-whoami": 'echo \'{"address": "testhost/operator"}\'',
    # agent-fabric-fleetdeck: `server` listens on STUB_SOCK; `session list`
    # names it; the rest answers nothing, as a server with no workspace would.
    "agent-fabric-fleetdeck": """
        case "$1" in
        server)
            echo started >> "$STUB_DIR/servers"
            echo "$SSH_AUTH_SOCK" >> "$STUB_DIR/server.agent"
            echo $$ >> "$STUB_DIR/server.pid"
            exec "$PYTHON" -c 'import socket,os,time
s=socket.socket(socket.AF_UNIX); s.bind(os.environ["STUB_SOCK"]); s.listen(8)
while True: c,_=s.accept(); c.close()'
            ;;
        session)
            printf '{"sessions":[{"name":"default","default":true,"socket_path":"%s"}]}\\n' "$STUB_SOCK"
            ;;
        *) echo '{}' ;;
        esac
    """,
}


def alive(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat") as handle:
            return handle.read().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def stat_fields(pid: int) -> list[str]:
    with open(f"/proc/{pid}/stat") as handle:
        return handle.read().rsplit(")", 1)[1].split()


def until(probe, seconds=10.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(0.05)
    return probe()


class AttachNoteTest(unittest.TestCase):
    def test_restart_is_offered_only_where_a_registration_mends_the_link(self):
        self.assertIn("`fleet-deck restart` mends", fleet_deck.attach_note(
            "herdr's panes' ssh-agent link /s.agent leads to no live agent (/s.unavailable)"))
        listing = f"... lists the key but cannot sign with it; {fleet_deck.boot.RESTART_SERVER}"
        self.assertEqual(fleet_deck.attach_note(listing), "attaching as before")


class FleetDeckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="fleet-deck-test-")
        bin_dir = os.path.join(self.dir, "bin")
        os.mkdir(bin_dir)
        for name, body in STUBS.items():
            path = os.path.join(bin_dir, name)
            with open(path, "w") as handle:
                handle.write("#!/bin/sh\n" + textwrap.dedent(body).lstrip())
            os.chmod(path, 0o755)
        # A Unix socket path is limited to 108 bytes: keep it short.
        runtime = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self.sock_dir = tempfile.mkdtemp(prefix="fd-", dir=runtime)
        env = {
            "PATH": bin_dir + os.pathsep + os.environ["PATH"],
            "XDG_STATE_HOME": os.path.join(self.dir, "state"),
            "STUB_DIR": self.dir,
            "STUB_SOCK": os.path.join(self.sock_dir, "s"),
            "PYTHON": sys.executable,
            # The deck's catalogue default must not reach the operator's checkout.
            "AGENT_FABRIC_ROOT": os.path.join(self.dir, "no-fabric"),
        }
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        # This host's moveto decides attach mode in a real boot; a test's is fixed.
        attach = mock.patch.object(fleet_deck, "attach_mode", return_value=False)
        attach.start()
        self.addCleanup(attach.stop)
        for name in ("HERDR_ENV", "HERDR_POPUP", "HERDR_SOCKET_PATH", "HERDR_SESSION",
                     "AGENT_FABRIC_FLEETDECK"):
            os.environ.pop(name, None)
        self.addCleanup(self.clean)
        self.said = []
        # Only passed on: no test here reaches it through ssh.
        self.agent = os.path.join(self.sock_dir, "agent")

    def clean(self):
        # Nothing a run started outlives it: the deck, its stream, the server.
        holder = lock_holder(lock_path())
        if holder:
            os.kill(holder, signal.SIGKILL)
        for name in ("stream.pid", "server.pid"):
            try:
                with open(os.path.join(self.dir, name)) as handle:
                    pids = [int(line) for line in handle.read().split()]
            except FileNotFoundError:
                continue
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.rmtree(self.sock_dir, ignore_errors=True)

    def say(self, line):
        self.said.append(line)

    def args(self):
        return SimpleNamespace(catalog=None, exclude=[], cwd=self.dir, no_fleet_tab=True)

    def stream_pid(self):
        path = os.path.join(self.dir, "stream.pid")
        if not os.path.exists(path):
            return None
        with open(path) as handle:
            text = handle.read().strip()
        return int(text) if text else None

    def test_start_twice_runs_one_detached_controller(self):
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        first = lock_holder(lock_path())
        self.assertTrue(first)
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        self.assertEqual(lock_holder(lock_path()), first)
        self.assertEqual(sum("starting the deck controller" in line for line in self.said), 1)
        fields = stat_fields(first)
        ppid, sid, tty = int(fields[1]), int(fields[3]), int(fields[4])
        self.assertNotEqual(ppid, os.getpid(), "the controller is no child of the command")
        # A session of its own, of which it is not the leader (double fork), so
        # it can never acquire a controlling terminal.
        self.assertNotEqual(sid, os.getsid(0), "the controller is in a session of its own")
        self.assertNotEqual(sid, first)
        self.assertEqual(tty, 0, "the controller has no terminal")
        self.assertEqual(os.readlink(f"/proc/{first}/fd/0"), os.devnull)
        self.assertEqual(os.readlink(f"/proc/{first}/fd/2"), fleet_deck.log_path())

    def test_stop_ends_the_controller_and_its_stream_child(self):
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        deck = lock_holder(lock_path())
        stream = until(self.stream_pid)
        self.assertTrue(stream and alive(stream), "the deck started its state stream")
        self.assertTrue(fleet_deck.stop_controller(self.say))
        self.assertIsNone(lock_holder(lock_path()))
        self.assertFalse(until(lambda: not alive(deck)) is False)
        self.assertTrue(until(lambda: not alive(stream)), "the stream child went with the deck")

    def test_restart_replaces_the_controller(self):
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        first = lock_holder(lock_path())
        self.assertTrue(fleet_deck.stop_controller(self.say))
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        second = lock_holder(lock_path())
        self.assertTrue(second)
        self.assertNotEqual(first, second)

    def test_a_second_deck_refuses_to_run(self):
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        holder = lock_holder(lock_path())
        second = subprocess.run(
            [fleet_deck.DECK, "--no-fleet-tab", "--cwd", self.dir],
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
        )
        self.assertEqual(second.returncode, 1)
        self.assertIn(f"another deck held the lock on this login (pid {holder})", second.stderr)
        self.assertEqual(lock_holder(lock_path()), holder)

    def test_the_server_is_started_once(self):
        self.assertIsNone(fleet_deck.server_up())
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        self.assertTrue(fleet_deck.server_up())
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        with open(os.path.join(self.dir, "servers")) as handle:
            self.assertEqual(handle.read().split(), ["started"])

    def test_status_says_what_runs(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(fleet_deck.status(self.say), 3)
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        self.said.clear()
        self.assertEqual(fleet_deck.status(self.say), 0)
        self.assertIn(f"deck controller: running, pid {lock_holder(lock_path())}", self.said)

    def test_start_refuses_inside_a_fleetdeck_pane(self):
        os.environ["HERDR_ENV"] = "1"
        os.environ["AGENT_FABRIC_FLEETDECK"] = "1"
        with mock.patch("sys.stderr"):
            self.assertEqual(fleet_deck.main(["start", "--no-fleet-tab"]), 2)
        self.assertIsNone(lock_holder(lock_path()))
        os.environ["HERDR_POPUP"] = "1"
        self.assertFalse(fleet_deck.in_herdr_pane(), "a popup is the operator's own command")

    def test_a_controller_that_dies_at_once_shows_its_log(self):
        with mock.patch.object(fleet_deck, "DECK", "false"), \
             mock.patch.object(fleet_deck, "CONTROLLER_READY_S", 1):
            self.assertFalse(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        self.assertTrue(any("did not start" in line for line in self.said))

    def test_the_prefix_is_said_and_a_colliding_one_is_named(self):
        config = os.path.join(self.dir, "config.toml")
        os.environ["HERDR_CONFIG_PATH"] = config
        self.assertEqual(fleet_deck.prefix_line(config), ("prefix: ctrl+6 (herdr's default)", True))
        with open(config, "w") as handle:
            handle.write('[keys]\nprefix = "ctrl+b"\n')
        line, checked = fleet_deck.prefix_line(config)
        self.assertFalse(checked)
        self.assertIn("ctrl+b", line)
        with open(config, "w") as handle:
            handle.write('[keys]\nprefix = ["ctrl+6", "ctrl+^"]\n')
        self.assertTrue(fleet_deck.prefix_line(config)[1])

    def test_a_probe_never_makes_a_starting_deck_refuse(self):
        # fleet-deck polls while a deck starts, and status may run at any
        # time: a deck taking the lock must never lose it to a probe. One
        # process takes and drops the lock over and over while this one probes.
        import threading

        path = lock_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "a").close()
        taker = subprocess.Popen(
            [sys.executable, "-B", "-c",
             "import os, sys; sys.path.insert(0, sys.argv[1]); from fabric_deck import hold_lock\n"
             "refused = 0\n"
             "for _ in range(3000):\n"
             "    fd = hold_lock(sys.argv[2])\n"
             "    if fd is None: refused += 1\n"
             "    else: os.close(fd)\n"
             "print(refused)", HERE, path],
            stdout=subprocess.PIPE, text=True)
        done = threading.Event()

        def probe():
            while not done.is_set():
                lock_holder(path)

        prober = threading.Thread(target=probe)
        prober.start()
        try:
            out, _ = taker.communicate(timeout=120)
        finally:
            done.set()
            prober.join()
        self.assertEqual(out.strip(), "0", "a probe made the deck's lock fail")

    def test_the_holder_is_the_kernels_answer(self):
        self.assertIsNone(lock_holder(lock_path()))
        fd = hold_lock(lock_path())
        self.assertIsNotNone(fd)
        child = subprocess.run(
            [sys.executable, "-B", "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); from fabric_deck import lock_holder; "
             "print(lock_holder(sys.argv[2]))", HERE, lock_path()],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(child.stdout.strip(), str(os.getpid()))
        os.close(fd)
        self.assertIsNone(lock_holder(lock_path()))

    def test_options_for_a_running_controller_are_said_to_wait_for_restart(self):
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        self.said.clear()
        args = self.args()
        args.exclude = ["someone"]
        self.assertTrue(fleet_deck.ensure_controller(args, self.say, self.agent))
        self.assertTrue(any("fleet-deck restart" in line for line in self.said), self.said)

    def test_a_missing_herdr_is_named(self):
        os.environ["PATH"] = os.path.join(self.dir, "empty")
        self.assertFalse(fleet_deck.ensure_server(self.say, self.agent))
        self.assertIn("agent-fabric-fleetdeck is not on PATH", self.said)

    def test_a_herdr_panes_context_is_not_the_decks(self):
        # Inside a pane a Herdr server started, its socket is another
        # product's: the deck neither counts itself in a pane nor reads it.
        os.environ["HERDR_ENV"] = "1"
        os.environ["HERDR_SOCKET_PATH"] = os.path.join(self.dir, "herdr.sock")
        self.assertFalse(fleet_deck.in_herdr_pane())
        self.assertEqual(fleet_deck.herdr_socket_path(), os.environ["STUB_SOCK"])

    def test_a_controller_that_cannot_be_run_says_so_in_its_log(self):
        with mock.patch.object(fleet_deck, "DECK", os.path.join(self.dir, "no-such-deck")), \
             mock.patch.object(fleet_deck, "CONTROLLER_READY_S", 1):
            self.assertFalse(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        self.assertTrue(any("cannot run" in line for line in self.said), self.said)

    def test_no_server_or_controller_starts_without_the_agent(self):
        self.assertFalse(fleet_deck.ensure_server(self.say, None))
        self.assertFalse(fleet_deck.ensure_controller(self.args(), self.say, None))
        self.assertIsNone(fleet_deck.server_up())
        self.assertIsNone(lock_holder(lock_path()))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "servers")))
        self.assertTrue(any("not started without the ssh-agent" in line for line in self.said))

    def test_the_server_inherits_the_agent(self):
        # herdr points its panes' link at the agent its server inherited.
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        with open(os.path.join(self.dir, "server.agent")) as handle:
            self.assertEqual(handle.read().split(), [self.agent])

    def test_a_running_server_with_a_dead_link_gets_a_holder_and_no_controller_without_it(self):
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        os.symlink(os.environ["STUB_SOCK"] + ".unavailable", os.environ["STUB_SOCK"] + ".agent")
        with mock.patch.object(fleet_deck.boot, "ensure_agent", return_value=self.agent), \
             mock.patch.object(fleet_deck, "probe_line", return_value=None), \
             mock.patch.object(fleet_deck, "moveto_list", return_value=""), \
             mock.patch.object(fleet_deck, "HOLD_READY_S", 1), \
             mock.patch.object(fleet_deck, "spawn_detached") as spawn, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(fleet_deck.main(["start", "--no-fleet-tab"]), 1)
        argv, _log = spawn.call_args.args
        self.assertEqual(argv[-3:], ["hold-agent", "--socket", self.agent])
        self.assertIn("leads to no live agent", stderr.getvalue())
        self.assertIsNone(lock_holder(lock_path()), "no controller arms panes with a dead link")

    def test_start_without_an_agent_starts_nothing(self):
        with mock.patch.object(fleet_deck.boot, "ensure_agent", return_value=None) as ensure:
            self.assertEqual(fleet_deck.main(["start", "--no-fleet-tab"]), 1)
        ensure.assert_called_once()
        self.assertIsNone(fleet_deck.server_up())
        self.assertIsNone(lock_holder(lock_path()))

    def test_a_refusing_sshd_stops_the_boot_before_anything_starts(self):
        with mock.patch.object(fleet_deck.boot, "ensure_agent", return_value=self.agent), \
             mock.patch.object(fleet_deck, "probe_line", return_value="sshd refused") as probe, \
             mock.patch.object(fleet_deck, "moveto_list", return_value="a-01 role\n"), \
             mock.patch("sys.stderr"):
            self.assertEqual(fleet_deck.main(["start", "--auto", "--no-fleet-tab"]), 1)
        probe.assert_called_once_with("a-01")
        self.assertIsNone(fleet_deck.server_up())
        self.assertIsNone(lock_holder(lock_path()))

    def test_a_plain_start_does_not_probe_sshd(self):
        with mock.patch.object(fleet_deck.boot, "ensure_agent", return_value=self.agent), \
             mock.patch.object(fleet_deck, "probe_line", return_value="refused") as probe, \
             mock.patch.object(fleet_deck, "boot_fleet") as booted, \
             mock.patch.object(fleet_deck, "ensure_link", return_value=True), \
             mock.patch("sys.stderr"):
            self.assertEqual(fleet_deck.main(["start", "--no-fleet-tab"]), 0)
        probe.assert_not_called()
        booted.assert_not_called()

    def test_an_attach_with_a_dead_link_still_attaches_and_says_how_to_mend_it(self):
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        os.symlink(os.environ["STUB_SOCK"] + ".unavailable", os.environ["STUB_SOCK"] + ".agent")
        with mock.patch.object(fleet_deck.boot, "ensure_agent") as ensure, \
             mock.patch.object(fleet_deck, "attach", return_value=0) as attach, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(fleet_deck.main([]), 0)
        ensure.assert_not_called()
        attach.assert_called_once()
        self.assertIn("fleet-deck restart", stderr.getvalue())

    def test_a_boot_that_cannot_read_the_tabs_fails(self):
        with mock.patch.object(fleet_deck, "moveto_list", side_effect=OSError("busy")), \
             mock.patch.object(fleet_deck, "local_host", return_value="testhost"), \
             mock.patch.object(fleet_deck, "TABS_READY_S", 0), \
             mock.patch.object(fleet_deck.boot, "activate") as activate:
            self.assertEqual(fleet_deck.boot_fleet(self.say, []), 1)
        activate.assert_not_called()
        self.assertTrue(any("nothing was activated" in line for line in self.said))

    def test_an_automatic_boot_holds_the_boot_lock_and_a_second_one_refuses(self):
        held = []
        with mock.patch.object(fleet_deck.boot, "ensure_agent", return_value=self.agent), \
             mock.patch.object(fleet_deck, "moveto_list", return_value="a-01 role\n"), \
             mock.patch.object(fleet_deck, "probe_line", return_value=None), \
             mock.patch.object(fleet_deck, "ensure_link", return_value=True), \
             mock.patch.object(fleet_deck, "control_agents", return_value=True), \
             mock.patch.object(fleet_deck, "boot_fleet",
                               side_effect=lambda *_: held.append(self.boot_lock_holder()) or 0), \
             mock.patch("sys.stderr"):
            self.assertEqual(fleet_deck.main(["start", "--auto", "--no-fleet-tab", "--cwd", self.dir]), 0)
        self.assertEqual(held, [os.getpid()], "the boot holds the lock while it activates")
        # A second boot while one runs: another process holds the lock.
        holder = subprocess.Popen(
            [sys.executable, "-B", "-c",
             "import sys, time; sys.path.insert(0, sys.argv[1]); from fabric_deck import hold_lock\n"
             "fd = hold_lock(sys.argv[2]); print('held', flush=True); time.sleep(30)",
             HERE, fabric_deck.boot_lock_path()], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        with mock.patch.object(fleet_deck.boot, "ensure_agent") as ensure, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(fleet_deck.main(["start", "--auto", "--no-fleet-tab"]), 1)
        ensure.assert_not_called()
        self.assertIn("another fleet-deck start --auto runs", stderr.getvalue())

    def boot_lock_holder(self):
        # Asked from another process: in the holder, F_GETLK reports no lock,
        # and closing its descriptor would drop the holder's own (hold_lock).
        child = subprocess.run(
            [sys.executable, "-B", "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); import fabric_deck; "
             "print(fabric_deck.lock_holder(fabric_deck.boot_lock_path()))", HERE],
            capture_output=True, text=True, timeout=30)
        out = child.stdout.strip()
        return int(out) if out.isdigit() else None

    def automatic_boot(self, attach):
        calls = []
        with mock.patch.object(fleet_deck.boot, "ensure_agent", return_value=self.agent), \
             mock.patch.object(fleet_deck, "moveto_list", return_value="a-01 role\n"), \
             mock.patch.object(fleet_deck, "probe_line", return_value=None), \
             mock.patch.object(fleet_deck, "ensure_link", return_value=True), \
             mock.patch.object(fleet_deck, "attach_mode", return_value=attach), \
             mock.patch.object(fleet_deck, "control_agents", side_effect=lambda op, say: calls.append(op) or False), \
             mock.patch.object(fleet_deck, "boot_fleet", side_effect=lambda *_: calls.append("boot") or 0), \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(fleet_deck.main(["start", "--auto", "--no-fleet-tab", "--cwd", self.dir]), 0)
        return calls, stderr.getvalue()

    def test_an_attach_mode_boot_starts_the_harness_units_before_the_panes(self):
        calls, said = self.automatic_boot(True)
        self.assertEqual(calls, ["control-start", "harness-start", "boot"])
        self.assertIn("some harness units did not start; going on with the panes", said)
        calls, said = self.automatic_boot(False)
        self.assertEqual(calls, ["control-start", "boot"], "no units without --attach")
        self.assertNotIn("harness units", said)

    def test_the_controller_reads_the_boot_lock(self):
        self.assertIsNone(lock_holder(fabric_deck.boot_lock_path()))
        fd = hold_lock(fabric_deck.boot_lock_path())
        self.addCleanup(os.close, fd)
        child = subprocess.run(
            [sys.executable, "-B", "-c",
             "import sys; sys.path.insert(0, sys.argv[1]); import fabric_deck; "
             "print(fabric_deck.lock_holder(fabric_deck.boot_lock_path()) is not None)", HERE],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(child.stdout.strip(), "True")

    def test_a_stale_state_record_is_unknown_and_a_fresh_one_counts(self):
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc)
        stale = (now - dt.timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        fresh = now.isoformat().replace("+00:00", "Z")
        rows = [json.dumps({"address": "testhost/old", "ts": stale, "state": "idle", "sessions": []}),
                json.dumps({"address": "testhost/new", "ts": fresh, "state": "idle", "sessions": []})]
        with mock.patch.object(fleet_deck, "local_host", return_value="testhost"), \
             mock.patch.object(fleet_deck, "states_snapshot", return_value=rows):
            fleet = fleet_deck.DeckFleet(self.say)
            self.assertEqual(fleet.live_counts(), {"old": None, "new": 0})

    def test_an_unlisted_fleet_stops_the_boot_before_anything_starts(self):
        with mock.patch.object(fleet_deck.boot, "ensure_agent", return_value=self.agent), \
             mock.patch.object(fleet_deck, "moveto_list", side_effect=subprocess.TimeoutExpired("moveto", 60)), \
             mock.patch.object(fleet_deck, "probe_line") as probe, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(fleet_deck.main(["start", "--auto", "--no-fleet-tab"]), 1)
        probe.assert_not_called()
        self.assertIn("cannot be probed", stderr.getvalue())
        self.assertIsNone(fleet_deck.server_up())

    def test_the_boot_tiers_a_coordinator_by_its_role_from_moveto_list(self):
        listed = "coord fabric-coordinator agent-fabric\ncto architect-cto agent-fabric\n"
        tab = lambda ws: mock.Mock(workspace_id=ws, panes={fleet_deck.HARNESS: "p"})
        herdr = mock.Mock(workspaces=mock.Mock(return_value=[{"workspace_id": "w1", "label": "C-Level"}]),
                          account_tabs=mock.Mock(return_value={"coord": tab("w1"), "cto": tab("w1")}))
        outcome = fleet_deck.boot.Outcome(up=["coord", "cto"])
        with mock.patch.object(fleet_deck, "moveto_list", return_value=listed), \
             mock.patch.object(fleet_deck, "Herdr", return_value=herdr), \
             mock.patch.object(fleet_deck.boot, "activate", return_value=outcome) as activate:
            self.assertEqual(fleet_deck.boot_fleet(self.say, []), 0)
        self.assertEqual(activate.call_args.args[1],
                         [(fleet_deck.boot.COORDINATOR, ["coord"]), ("C-Level", ["cto"])])

    def test_stop_all_ends_a_coordinator_in_c_level_last(self):
        listed = "coord fabric-coordinator agent-fabric\ncto architect-cto agent-fabric\nops devex-tooling x\n"
        tab = lambda ws: mock.Mock(workspace_id=ws, panes={fleet_deck.HARNESS: "p"})
        herdr = mock.Mock(workspaces=mock.Mock(return_value=[{"workspace_id": "w1", "label": "C-Level"},
                                                             {"workspace_id": "w2", "label": "Infrastructure"}]),
                          account_tabs=mock.Mock(return_value={"coord": tab("w1"), "cto": tab("w1"),
                                                               "ops": tab("w2")}))
        group = {"coord": 1, "cto": 2, "ops": 3}
        ended = []
        with mock.patch.object(fleet_deck, "moveto_list", return_value=listed), \
             mock.patch.object(fleet_deck, "Herdr", return_value=herdr), \
             mock.patch.object(fleet_deck.DeckFleet, "moveto",
                               lambda self, login: (object(), {"foreground_process_group_id": group[login]})), \
             mock.patch.object(fleet_deck.DeckFleet, "up", lambda self, login: False), \
             mock.patch.object(fleet_deck.boot, "hang_up",
                               side_effect=lambda g: ended.append({v: k for k, v in group.items()}[g]) or True):
            fleet_deck.stop_sessions(self.say)
        self.assertEqual(ended, ["ops", "cto", "coord"], "the reverse of the boot order")

    def test_a_pane_is_not_waiting_while_its_session_state_is_unknown(self):
        with mock.patch.object(fleet_deck, "local_host", return_value="testhost"):
            fleet = fleet_deck.DeckFleet(self.say)
        fleet.harness = {"a": "p1"}
        fleet.read_at = time.monotonic() + 3600  # the cached counts below stand
        fleet.moveto = mock.Mock(return_value=(mock.Mock(pid=7, mode=fleet_deck.WAIT), {}))
        fleet.herdr = mock.Mock(text=mock.Mock(return_value="a - Enter to activate\n"))
        fleet.live = {"a": 1}
        self.assertIsNone(fleet.waiting("a"))
        self.assertEqual(self.said, [], "a login that is up is not said to lack a record")
        for counts, expected in (({}, None), ({"a": None}, None), ({"a": 0}, 7)):
            fleet.live = counts
            self.assertEqual(fleet.waiting("a"), expected, counts)
        self.assertEqual(sum("no fresh state record" in line for line in self.said), 1,
                         "the reason is said, once, and not for a login that is up")

    def attach_fleet(self, focused=False):
        with mock.patch.object(fleet_deck, "local_host", return_value="testhost"):
            fleet = fleet_deck.DeckFleet(self.say, attach=True)
        fleet.harness, fleet.tab_id = {"a": "p1"}, {"a": "t1"}
        fleet.sleep = lambda s: None
        fleet.lock_dir = self.dir
        fleet.read_at = time.monotonic() + 3600  # the cached counts below stand
        fleet.live = {"a": 0}
        workspace = {"workspace_id": "w1", "focused": True, "active_tab_id": "t1" if focused else "t9"}
        # As herdr answers an attach's pane: the prompt on the screen, nothing in `recent`.
        def text(*args):
            if args[:2] == ("pane", "read"):
                return "a - Enter to activate\n" if args[args.index("--source") + 1] == "visible" else ""
            return ""
        fleet.herdr = mock.Mock(workspaces=mock.Mock(return_value=[workspace]), text=mock.Mock(side_effect=text))
        return fleet

    def test_an_attach_mode_boot_attaches_an_unfocused_bare_pane_and_presses_at_its_prompt(self):
        fleet = self.attach_fleet()
        fleet.moveto = mock.Mock(return_value=(None, {"shell_pid": 5, "foreground_process_group_id": 5,
                         "foreground_processes": [{"pid": 5, "argv": ["bash"]}]}))
        self.assertIsNone(fleet.waiting("a"))
        runs = [c.args for c in fleet.herdr.text.call_args_list if c.args[:2] == ("pane", "run")]
        self.assertEqual(runs, [("pane", "run", "p1", "moveto a --attach")])
        fleet.moveto = mock.Mock(return_value=(mock.Mock(pid=7, mode=fleet_deck.ATTACH), {}))
        self.assertEqual(fleet.waiting("a"), 7, "the prompt the attach mirrors is pressed")

    def test_an_attach_mode_boot_starts_an_attach_at_most_twice_the_focused_tabs_too(self):
        # While the boot runs the controller attaches no harness pane of an
        # account that is not up, so the boot reaches the focused tab's
        # prompt itself.
        bare = (None, {"shell_pid": 5, "foreground_process_group_id": 5,
                         "foreground_processes": [{"pid": 5, "argv": ["bash"]}]})
        focused = self.attach_fleet(focused=True)
        focused.moveto = mock.Mock(return_value=bare)
        focused.waiting("a")
        self.assertEqual([c.args for c in focused.herdr.text.call_args_list if c.args[:2] == ("pane", "run")],
                         [("pane", "run", "p1", "moveto a --attach")])
        fleet = self.attach_fleet()
        fleet.moveto = mock.Mock(return_value=bare)
        clock = [0.0]
        fleet.read_at = 1e9  # the cached counts stand on this clock too
        with mock.patch.object(fleet_deck.time, "monotonic", side_effect=lambda: clock[0]):
            for at in (0.0, 1.0, 10.0, 20.0, 30.0):
                clock[0] = at
                fleet.waiting("a")
        runs = [c for c in fleet.herdr.text.call_args_list if c.args[:2] == ("pane", "run")]
        self.assertEqual(len(runs), fleet_deck.ATTACH_STARTS)

    def test_stop_all_counts_a_harness_of_its_own_as_the_panes_even_when_its_hang_up_failed(self):
        listed = "ui rust-ui-dev x\nqa rust-ui-dev x\nox rust-ui-dev x\n"
        tab = lambda ws: mock.Mock(workspace_id=ws, panes={fleet_deck.HARNESS: "p"})
        herdr = mock.Mock(workspaces=mock.Mock(return_value=[{"workspace_id": "w1", "label": "Rust"}]),
                          account_tabs=mock.Mock(return_value={"ui": tab("w1"), "qa": tab("w1"),
                                                               "ox": tab("w1")}))

        def moveto(self, login):
            if login == "ox":
                raise RuntimeError("herdr busy")
            return (mock.Mock(mode=fleet_deck.ATTACH if login == "ui" else fleet_deck.WAIT),
                    {"foreground_process_group_id": 3})
        with mock.patch.object(fleet_deck, "moveto_list", return_value=listed), \
             mock.patch.object(fleet_deck, "Herdr", return_value=herdr), \
             mock.patch.object(fleet_deck, "attach_mode", return_value=True), \
             mock.patch.object(fleet_deck.DeckFleet, "moveto", moveto), \
             mock.patch.object(fleet_deck.DeckFleet, "up", lambda self, login: False), \
             mock.patch.object(fleet_deck.boot, "hang_up", return_value=False):
            deck, in_units = fleet_deck.stop_sessions(self.say)
        self.assertEqual(in_units, {"ui"}, "qa's --wait and the unread ox were their panes'")

    def test_the_boots_attach_and_line_go_through_the_lock(self):
        fleet = self.attach_fleet()
        bare = (None, {"shell_pid": 5, "foreground_process_group_id": 5,
                         "foreground_processes": [{"pid": 5, "argv": ["bash"]}]})
        fleet.moveto = mock.Mock(return_value=bare)
        with mock.patch.object(fleet_deck, "typed_at_bare_shell", return_value=False) as locked:
            fleet.waiting("a")
        self.assertEqual(locked.call_args.kwargs.get("wait"), True)
        self.assertFalse([c for c in fleet.herdr.text.call_args_list if c.args[:2] in
                          (("pane", "run"), ("pane", "send-keys"))], "nothing typed past a refusal")
        self.assertNotIn("a", fleet.attached, "a start refused is not counted")
        fleet.attached = {"a": (1, 0.0)}
        attach = (mock.Mock(pid=7, mode=fleet_deck.ATTACH), {"foreground_process_group_id": 7})
        fleet.moveto = mock.Mock(side_effect=[attach, bare])
        with mock.patch.object(fleet_deck, "typed_at_bare_shell", return_value=False) as locked, \
             mock.patch.object(fleet_deck.boot, "hang_up", return_value=True):
            fleet.done("a")
        self.assertEqual(locked.call_args.kwargs.get("wait"), False, "the line, after the hang-up")
        self.assertNotIn(mock.call("pane", "run", "p1", fleet_deck.DETACHED_COMMAND),
                         fleet.herdr.text.call_args_list)

    def test_done_ends_the_boots_attach_and_says_the_agent_runs_on(self):
        fleet = self.attach_fleet()
        fleet.attached = {"a": (1, 0.0)}
        attach = (mock.Mock(pid=7, mode=fleet_deck.ATTACH), {"foreground_process_group_id": 7})
        bare = (None, {"shell_pid": 5, "foreground_process_group_id": 5,
                         "foreground_processes": [{"pid": 5, "argv": ["bash"]}]})
        fleet.moveto = mock.Mock(side_effect=[attach, bare, bare])
        with mock.patch.object(fleet_deck.boot, "hang_up", return_value=True) as hang_up:
            fleet.done("a")
        hang_up.assert_called_once_with(7)
        fleet.herdr.text.assert_called_with("pane", "run", "p1", fleet_deck.DETACHED_COMMAND)

    def test_done_types_no_line_into_a_tab_a_person_opened_meanwhile(self):
        fleet = self.attach_fleet()
        fleet.attached = {"a": (1, 0.0)}
        attach = (mock.Mock(pid=7, mode=fleet_deck.ATTACH), {"foreground_process_group_id": 7})
        bare = (None, {"shell_pid": 5, "foreground_process_group_id": 5,
                         "foreground_processes": [{"pid": 5, "argv": ["bash"]}]})
        fleet.moveto = mock.Mock(side_effect=[attach, bare, bare])
        fleet._focused = mock.Mock(side_effect=[False, True])   # opened after the hang-up
        with mock.patch.object(fleet_deck.boot, "hang_up", return_value=True):
            fleet.done("a")
        self.assertNotIn(mock.call("pane", "run", "p1", fleet_deck.DETACHED_COMMAND),
                         fleet.herdr.text.call_args_list, "the controller attaches it, the account being up")

    def test_done_leaves_a_focused_tab_and_a_pane_the_boot_did_not_attach(self):
        focused, not_ours = self.attach_fleet(focused=True), self.attach_fleet()
        focused.attached = {"a": (1, 0.0)}
        for fleet in (focused, not_ours):
            fleet.moveto = mock.Mock(return_value=(mock.Mock(pid=7, mode=fleet_deck.ATTACH),
                                                   {"foreground_process_group_id": 7}))
            with mock.patch.object(fleet_deck.boot, "hang_up") as hang_up:
                fleet.done("a")
            hang_up.assert_not_called()

    def test_stop_all_never_hangs_up_an_attach(self):
        listed = "ui rust-ui-dev x\nqa rust-ui-dev x\n"
        tab = lambda ws: mock.Mock(workspace_id=ws, panes={fleet_deck.HARNESS: "p"})
        herdr = mock.Mock(workspaces=mock.Mock(return_value=[{"workspace_id": "w1", "label": "Rust"}]),
                          account_tabs=mock.Mock(return_value={"ui": tab("w1"), "qa": tab("w1")}))
        mode = {"ui": fleet_deck.ATTACH, "qa": fleet_deck.WAIT}
        with mock.patch.object(fleet_deck, "moveto_list", return_value=listed), \
             mock.patch.object(fleet_deck, "Herdr", return_value=herdr), \
             mock.patch.object(fleet_deck, "attach_mode", return_value=True), \
             mock.patch.object(fleet_deck.DeckFleet, "moveto",
                               lambda self, login: (mock.Mock(mode=mode[login]),
                                                    {"foreground_process_group_id": 3})), \
             mock.patch.object(fleet_deck.DeckFleet, "up", lambda self, login: False), \
             mock.patch.object(fleet_deck.boot, "hang_up", return_value=True) as hang_up:
            deck, in_units = fleet_deck.stop_sessions(self.say)
        hang_up.assert_called_once_with(3)   # qa's --wait, its agent in the pane
        self.assertEqual((deck, in_units), ({"ui", "qa"}, {"ui"}), "qa's was ended here, ui's runs on")
        self.assertTrue(any("attached, so not stopped here: ui" in line for line in self.said))
        self.assertTrue(any("accounts' own servers" in line for line in self.said))

    def test_stop_all_in_attach_mode_says_the_units_sessions_run_on_not_that_the_stream_lags(self):
        with mock.patch.object(fleet_deck, "stop_controller", return_value=True), \
             mock.patch.object(fleet_deck, "server_up", return_value=None), \
             mock.patch.object(fleet_deck, "stop_holder"), \
             mock.patch.object(fleet_deck, "control_agents", return_value=True), \
             mock.patch.object(fleet_deck.DeckFleet, "live_counts", return_value={"ui": 1, "qa": 1}), \
             mock.patch.object(fleet_deck, "local_host", return_value="testhost"):
            fleet_deck.server_up.side_effect = [object(), None]
            with mock.patch.object(fleet_deck, "stop_sessions", return_value=({"ui", "qa"}, {"ui"})), \
                 mock.patch.object(fleet_deck.subprocess, "run"), \
                 mock.patch.object(fleet_deck, "wait_for", return_value=True):
                fleet_deck.stop_all(self.say)
        self.assertTrue(any(line == "left running in their accounts' own servers: ui" for line in self.said))
        lag = [line for line in self.said if "can lag" in line]
        self.assertEqual(len(lag), 1)
        self.assertIn("qa", lag[0])
        self.assertNotIn("ui", lag[0])

    def stop_all_in_attach_mode(self, harness_stop):
        """stop_all with the deck gone, attach mode on, the stream showing ui
        (its session in its unit) and qa (ended in its pane) live."""
        calls = []

        def control(op, say):
            calls.append(op)
            return harness_stop if op == "harness-stop" else True

        with mock.patch.object(fleet_deck, "stop_controller", return_value=True), \
             mock.patch.object(fleet_deck, "server_up", side_effect=[object(), None]), \
             mock.patch.object(fleet_deck, "stop_holder"), \
             mock.patch.object(fleet_deck, "attach_mode", return_value=True), \
             mock.patch.object(fleet_deck, "control_agents", side_effect=control), \
             mock.patch.object(fleet_deck.DeckFleet, "live_counts", return_value={"ui": 1, "qa": 1}), \
             mock.patch.object(fleet_deck, "local_host", return_value="testhost"), \
             mock.patch.object(fleet_deck, "stop_sessions", return_value=({"ui", "qa"}, {"ui"})), \
             mock.patch.object(fleet_deck.subprocess, "run"), \
             mock.patch.object(fleet_deck, "wait_for", return_value=True):
            return fleet_deck.stop_all(self.say), calls

    def test_stop_all_in_attach_mode_stops_the_harness_units_before_the_control_agents(self):
        code, calls = self.stop_all_in_attach_mode(True)
        self.assertEqual((code, calls), (0, ["harness-stop", "control-stop"]))
        self.assertFalse(any("own servers" in line for line in self.said), "the unit's session was stopped")
        lag = [line for line in self.said if "can lag" in line]
        self.assertEqual(len(lag), 1)
        self.assertIn("qa, ui", lag[0])

    def test_a_failed_harness_stop_fails_stop_all_and_names_the_sessions_left_in_their_units(self):
        code, calls = self.stop_all_in_attach_mode(False)
        self.assertEqual((code, calls), (1, ["harness-stop", "control-stop"]))
        self.assertIn("left running in their accounts' own servers: ui", self.said)

    def test_a_fabric_ctl_without_harness_stop_leaves_the_units_running_and_says_so(self):
        code, _ = self.stop_all_in_attach_mode(None)
        self.assertEqual(code, 0, "nothing failed: there was nothing to run")
        self.assertIn("left running in their accounts' own servers: ui", self.said)

    def test_control_agents_says_which_units_and_none_when_fabric_ctl_lacks_the_op(self):
        with mock.patch.object(fleet_deck, "fabric_ctl_has", return_value=False):
            self.assertIsNone(fleet_deck.control_agents("harness-stop", self.say))
        self.assertEqual(self.said[-1], "harness units: fabric-ctl has no harness-stop yet; left as they are")
        done = subprocess.CompletedProcess([], 1, "x-01  failed  timeout\n", "")
        with mock.patch.object(fleet_deck, "fabric_ctl_has", return_value=True), \
             mock.patch.object(fleet_deck.subprocess, "run", return_value=done) as run:
            self.assertIs(fleet_deck.control_agents("harness-stop", self.say), False)
            self.assertIs(fleet_deck.control_agents("control-stop", self.say), False)
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [["fabric-ctl", "all", "harness-stop"], ["fabric-ctl", "all", "control-stop"]])
        self.assertEqual([c.kwargs["timeout"] for c in run.call_args_list],
                         [fleet_deck.HARNESS_CTL_S, fleet_deck.CONTROL_CTL_S])
        self.assertEqual(self.said[-2:], ["harness units: x-01  failed  timeout", "control agents: x-01  failed  timeout"])

    def test_stop_all_goes_on_when_the_server_stop_fails_and_shows_logins_printable(self):
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        real_run = subprocess.run

        def failing_stop(argv, **kw):
            if argv[1:] == ["server", "stop"]:
                raise subprocess.TimeoutExpired(argv, 60)
            return real_run(argv, **kw)

        with mock.patch.object(fleet_deck, "stop_sessions", return_value=(set(), set())), \
             mock.patch.object(fleet_deck.subprocess, "run", side_effect=failing_stop), \
             mock.patch.object(fleet_deck, "SERVER_STOP_S", 0), \
             mock.patch.object(fleet_deck, "stop_holder") as holder, \
             mock.patch.object(fleet_deck, "control_agents", return_value=True) as control, \
             mock.patch.object(fleet_deck.DeckFleet, "live_counts", return_value={"x\x1b]52;c;Zm9v\x07": 1}), \
             mock.patch.object(fleet_deck, "local_host", return_value="testhost"):
            self.assertEqual(fleet_deck.stop_all(self.say), 1)
        holder.assert_called_once()
        control.assert_called_once()
        self.assertFalse(any("\x1b" in line or "\x07" in line for line in self.said), self.said)

    def test_auto_and_all_go_with_their_verbs(self):
        for argv in (["attach", "--auto"], ["stop", "--auto"], ["start", "--all"], ["stop", "--confirm"]):
            with self.subTest(argv=argv), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                fleet_deck.main(argv)

    def test_stop_all_refuses_inside_a_pane_but_the_popup_asks(self):
        os.environ["HERDR_ENV"] = "1"
        os.environ["AGENT_FABRIC_FLEETDECK"] = "1"
        with mock.patch("sys.stderr"):
            self.assertEqual(fleet_deck.main(["stop", "--all"]), 2)
        with mock.patch("sys.stderr"), mock.patch.object(fleet_deck, "spawn_detached") as spawn:
            self.assertEqual(fleet_deck.main(["stop", "--all", "--confirm"]), 2,
                             "an ordinary pane is refused, not told it is stopping")
        spawn.assert_not_called()
        os.environ["HERDR_POPUP"] = "1"
        with mock.patch("builtins.input", return_value="yes"), mock.patch("sys.stdout"), \
             mock.patch.object(fleet_deck, "spawn_detached") as spawn:
            self.assertEqual(fleet_deck.main(["stop", "--all", "--confirm"]), 1)
        spawn.assert_not_called()
        with mock.patch("builtins.input", return_value="stop"), mock.patch("sys.stdout"), \
             mock.patch.object(fleet_deck, "spawn_detached") as spawn:
            self.assertEqual(fleet_deck.main(["stop", "--all", "--confirm"]), 0)
        argv, log = spawn.call_args.args
        self.assertEqual(argv[-2:], ["stop", "--all"])
        self.assertEqual(log, fleet_deck.log_path())

    def test_stop_all_ends_the_controller_and_the_server(self):
        self.assertTrue(fleet_deck.ensure_server(self.say, self.agent))
        self.assertTrue(fleet_deck.ensure_controller(self.args(), self.say, self.agent))
        server = fleet_deck.server_up()[0]

        real_run = subprocess.run
        stopped = []

        def server_stop(argv, **kw):
            # The stub server has no stop; everything else runs as it is.
            if argv[1:] != ["server", "stop"]:
                return real_run(argv, **kw)
            stopped.append(argv)
            os.kill(server, signal.SIGKILL)
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch.object(fleet_deck, "stop_sessions", return_value=(set(), set())) as sessions, \
             mock.patch.object(fleet_deck.subprocess, "run", side_effect=server_stop), \
             mock.patch.object(fleet_deck, "control_agents", return_value=True) as control, \
             mock.patch.object(fleet_deck.DeckFleet, "live_counts", return_value={}), \
             mock.patch.object(fleet_deck, "local_host", return_value="testhost"):
            self.assertEqual(fleet_deck.stop_all(self.say), 0)
        sessions.assert_called_once()
        self.assertEqual(stopped, [[fleet_deck.BIN, "server", "stop"]])
        control.assert_called_once_with("control-stop", self.say)
        self.assertIsNone(lock_holder(lock_path()))
        self.assertTrue(until(lambda: fleet_deck.server_up() is None))

    def test_stop_never_signals_a_pid_it_cannot_see(self):
        with mock.patch.object(fleet_deck, "lock_holder", lambda _path: 0), \
             mock.patch.object(fleet_deck.os, "kill") as kill:
            self.assertFalse(fleet_deck.stop_controller(self.say))
        kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
