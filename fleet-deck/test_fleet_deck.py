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

        with mock.patch.object(fleet_deck, "stop_sessions") as sessions, \
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
