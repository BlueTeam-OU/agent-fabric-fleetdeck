"""fleet-deck: the one command that brings the Fleet Deck back.

`fleet-deck` makes sure herdr's server runs, makes sure one deck controller
(fabric-deck) runs detached, then attaches this terminal to herdr. Run twice,
it starts nothing twice: the server answers its socket, and the controller
holds a record lock (fabric_deck.hold_lock) that a second one cannot take.

The controller is started in a session of its own with no terminal: its
stdin is /dev/null and its output goes to a log file, so closing a terminal
or a herdr tab never reaches it, and it is stopped by `fleet-deck stop`
(SIGTERM), never by a key. It is double-forked, so it is no child of the
herdr client this command becomes and is reaped by init.

`fleet-deck stop` stops the controller only. herdr's server keeps every
agent's pane alive; stopping it (`herdr server stop`) ends every pane's
process, so only `stop --all`, which means to end everything, does.

No server and no controller is started without a live ssh-agent holding
the deck key, and `start --auto` activates the fleet tier by tier
(boot.py says why and how).
"""

from __future__ import annotations

import datetime
import getpass
import os
import shutil
import signal
import subprocess
import sys
import time
from typing import Callable, Iterable

import boot
from deck_tabs import HARNESS, WAIT, moveto_in
from fabric_deck import (
    BIN,
    BOARD_DIR,
    PANE_MARKER,
    Herdr,
    fleetdeck_env,
    for_this_host,
    herdr_socket_path,
    live_of,
    local_host,
    hold_lock,
    lock_holder,
    lock_path,
    moveto_list,
    parse_moveto_list,
    parse_state_line,
    server_instance,
    state_dir,
    states_snapshot,
)

DECK = os.path.join(BOARD_DIR, "fabric-deck")

# How long a just-started server or controller has to show itself before
# the command says it did not come up.
SERVER_READY_S = 15
CONTROLLER_READY_S = 10
# How long a stopped controller has to exit: the deck itself gives its state
# stream child 5 s (fabric_deck.STOP_CHILD_GRACE_S) before killing it.
CONTROLLER_STOP_S = 10
# The log is kept to one previous generation, rotated when a controller starts.
LOG_ROTATE_BYTES = 1 << 20


def log_path() -> str:
    return os.path.join(state_dir(), "deck.log")


def in_herdr_pane() -> bool:
    """Whether this process runs inside a FleetDeck pane. FleetDeck marks a
    pane's environment with HERDR_ENV=1 and AGENT_FABRIC_FLEETDECK=1, and a
    popup's with HERDR_POPUP=1 as well; a popup is the operator's own
    configured command and may drive the deck. A Herdr pane is not one."""
    env = fleetdeck_env()
    return env.get(PANE_MARKER) == "1" and env.get("HERDR_POPUP") != "1"


# The prefix herdr's tests check against every harness's keys
# (src/client/shell/tests/harness_keys.rs); 0x1e on a legacy host is ctrl+^.
CHECKED_PREFIXES = frozenset({"ctrl+6", "ctrl+^"})


def herdr_config_path() -> str:
    """FleetDeck's config file, as it resolves it (src/config/io.rs config_path)."""
    env = fleetdeck_env()
    if env.get("HERDR_CONFIG_PATH"):
        return env["HERDR_CONFIG_PATH"]
    base = env.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, BIN, "config.toml")


def configured_prefix(path: str) -> list[str] | None:
    """keys.prefix as the config sets it, or None when it leaves herdr's
    default (ctrl+6) or cannot be read."""
    import tomllib

    try:
        with open(path, "rb") as handle:
            prefix = tomllib.load(handle).get("keys", {}).get("prefix")
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(prefix, str):
        return [prefix]
    if isinstance(prefix, list) and all(isinstance(p, str) for p in prefix):
        return prefix
    return None


def prefix_line(path: str) -> tuple[str, bool]:
    """What the prefix is, and whether it is one the harness check covers."""
    prefix = configured_prefix(path)
    if prefix is None:
        return "prefix: ctrl+6 (herdr's default)", True
    shown = " / ".join(prefix)
    checked = all(p.strip().lower().replace(" ", "") in CHECKED_PREFIXES for p in prefix)
    return f"prefix: {shown} (keys.prefix in {path})", checked


def default_catalog() -> str | None:
    """The role catalogue the deck seeds workspaces from: the agent-fabric
    checkout's, AGENT_FABRIC_ROOT else ~/projects/agent-fabric, when it exists."""
    root = os.environ.get("AGENT_FABRIC_ROOT") or os.path.expanduser("~/projects/agent-fabric")
    path = os.path.join(root, "identities", "roles", "catalog.json")
    return path if os.path.exists(path) else None


def spawn_detached(argv: list[str], log: str | None, env: dict[str, str] | None = None) -> None:
    """Run `argv` in a new session, with no terminal, as a grandchild that
    init adopts at once. stdin is /dev/null; stdout and stderr append to
    `log`, or /dev/null without one. `env` replaces the environment."""
    pid = os.fork()
    if pid:
        os.waitpid(pid, 0)
        return
    try:
        os.setsid()
        if os.fork():
            os._exit(0)
        null = os.open(os.devnull, os.O_RDWR)
        out = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600) if log else null
        os.dup2(null, 0)
        os.dup2(out, 1)
        os.dup2(out, 2)
        os.closerange(3, os.sysconf("SC_OPEN_MAX") if hasattr(os, "sysconf") else 1024)
        # The stop and interrupt the deck relies on: never inherit an ignore.
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.execvpe(argv[0], argv, os.environ if env is None else env)
    except OSError as error:
        # stderr is the log here (or /dev/null): the caller tails the log.
        os.write(2, f"fleet-deck: cannot run {argv[0]}: {error}\n".encode())
    finally:
        os._exit(127)


def wait_for(probe: Callable[[], object], seconds: float, step: float = 0.2):
    deadline = time.monotonic() + seconds
    while True:
        value = probe()
        if value or time.monotonic() >= deadline:
            return value
        time.sleep(step)


def server_up() -> tuple[int, int] | None:
    return server_instance(herdr_socket_path())


def ensure_server(say: Callable[[str], None], agent: str | None) -> bool:
    if server_up():
        return True
    if shutil.which(BIN) is None:
        say(f"{BIN} is not on PATH")
        return False
    if agent is None:
        # Its panes would get no live agent, and each would ask for the
        # deck key's passphrase (boot.py's docstring).
        say(f"{BIN}'s server is not started without the ssh-agent holding the deck key")
        return False
    say(f"starting {BIN}'s server (its panes use the ssh-agent at {agent})")
    spawn_detached([BIN, "server"], None, dict(os.environ, SSH_AUTH_SOCK=agent))
    if wait_for(server_up, SERVER_READY_S):
        return True
    # herdr writes its own log; its stderr is /dev/null once detached.
    say(f"herdr's server did not answer within {SERVER_READY_S}s; "
        f"`{BIN} server` in a terminal shows why")
    return False


def rotate_log(path: str) -> None:
    try:
        if os.path.getsize(path) > LOG_ROTATE_BYTES:
            os.replace(path, path + ".1")
    except FileNotFoundError:
        pass


def log_tail(path: str, lines: int = 5) -> list[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()[-lines:]
    except FileNotFoundError:
        return []


def deck_argv(args) -> list[str]:
    argv = [DECK]
    catalog = args.catalog or default_catalog()
    if catalog:
        argv += ["--catalog", catalog]
    for login in args.exclude:
        argv += ["--exclude", login]
    if args.cwd:
        argv += ["--cwd", args.cwd]
    if args.no_fleet_tab:
        argv.append("--no-fleet-tab")
    return argv


def deck_options_given(args) -> bool:
    return bool(args.catalog or args.exclude or args.cwd or args.no_fleet_tab)


def ensure_controller(args, say: Callable[[str], None], agent: str | None) -> bool:
    holder = lock_holder(lock_path())
    if holder is not None:
        if deck_options_given(args):
            say(f"the deck controller already runs (pid {holder}); its options are unchanged "
                "(fleet-deck restart <options> applies them)")
        return True
    if agent is None:
        # It arms panes, and a pane's ssh with no live agent asks for the passphrase.
        say("the deck controller is not started without the ssh-agent holding the deck key")
        return False
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    log = log_path()
    rotate_log(log)
    say(f"starting the deck controller (log: {log})")
    spawn_detached(deck_argv(args), log)
    if wait_for(lambda: lock_holder(lock_path()), CONTROLLER_READY_S):
        return True
    say(f"the deck controller did not start within {CONTROLLER_READY_S}s; its log ends:")
    for line in log_tail(log):
        say(f"  {line}")
    return False


def stop_controller(say: Callable[[str], None]) -> bool:
    holder = lock_holder(lock_path())
    if holder is None:
        say("the deck controller is not running")
        return True
    if holder <= 0:
        # The kernel reports 0 for a holder in another pid namespace, and
        # kill(0) would signal this command's own process group.
        say("the deck controller runs where this command cannot see its pid; "
            "stop it from the namespace it runs in")
        return False
    try:
        os.kill(holder, signal.SIGTERM)
    except ProcessLookupError:
        pass
    if wait_for(lambda: lock_holder(lock_path()) is None, CONTROLLER_STOP_S):
        say(f"the deck controller (pid {holder}) stopped")
        return True
    say(f"the deck controller (pid {holder}) did not stop within {CONTROLLER_STOP_S}s")
    return False


def status(say: Callable[[str], None]) -> int:
    server = server_up()
    holder = lock_holder(lock_path())
    say(f"herdr server: {'running, pid %d' % server[0] if server else 'not running'}")
    say(f"deck controller: {'running, pid %d' % holder if holder is not None else 'not running'}")
    if server:
        problem = boot.link_problem(herdr_socket_path())
        say(problem or "panes' ssh-agent: live")
    agent_holder = lock_holder(hold_lock_path())
    if agent_holder is not None:
        say(f"ssh-agent holder: running, pid {agent_holder}")
    say(f"log: {log_path()}")
    say(prefix_line(herdr_config_path())[0])
    # LSB status codes: 0 running, 3 not running.
    return 0 if server and holder is not None else 3


def attach() -> int:
    os.execvp(BIN, [BIN])
    return 127  # not reached


# ------------------------------------------------------------- the fleet

# How long a just-started controller has to give every account its tab
# before the boot plans the tiers with the tabs there are.
TABS_READY_S = 60
HOLD_READY_S = 10
HOLD_STOP_S = 5
# How long stopping one tier's sessions may take before the next.
TIER_STOP_S = 30
SERVER_STOP_S = 15


class DeckFleet:
    """boot.Fleet's facts and press, from herdr's CLI, moveto --list and the
    state stream's snapshot."""

    def __init__(self, say: Callable[[str], None], exclude: Iterable[str] = ()):
        self.herdr = Herdr()
        self.say = say
        self.host = local_host()
        # The deck's own exclusions (fabric_deck.main): an account left out has no tab to wait for.
        self.exclude = {getpass.getuser(), *exclude}
        self.harness: dict[str, str] = {}
        self.workspace: dict[str, str | None] = {}
        self.logins: list[str] = []
        self.live: dict[str, int] = {}
        self.read_at: float | None = None

    def read_map(self) -> None:
        self.logins = [a.login for a in parse_moveto_list(moveto_list(), self.exclude)]
        labels = {w["workspace_id"]: w.get("label") for w in self.herdr.workspaces()}
        tabs = self.herdr.account_tabs(set(self.logins))
        self.harness = {login: tab.panes[HARNESS] for login, tab in tabs.items() if HARNESS in tab.panes}
        self.workspace = {login: labels.get(tabs[login].workspace_id) for login in self.harness}

    def await_tabs(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while True:
            try:
                self.read_map()
            except Exception as error:  # herdr or moveto busy: read again until the deadline
                self.say(f"cannot read the deck's tabs yet ({boot.shown(str(error))})")
            if (self.logins and set(self.logins) <= set(self.harness)) or time.monotonic() >= deadline:
                break
            time.sleep(2)
        missing = sorted(set(self.logins) - set(self.harness))
        if missing:
            self.say(f"no harness pane yet for {', '.join(missing)}: not activated")

    def live_counts(self) -> dict[str, int]:
        """Live sessions per login on this host, read at most every POLL_S."""
        now = time.monotonic()
        if self.read_at is None or now - self.read_at >= boot.POLL_S:
            self.read_at = now
            utc = datetime.datetime.now(datetime.timezone.utc)
            self.live = {}
            for line in states_snapshot(lambda _line: None):
                record = parse_state_line(line)
                if for_this_host(record, self.host):
                    live = live_of(record, utc)
                    self.live[record.login] = live.count if live is not None else 0
        return self.live

    def up(self, login: str) -> bool:
        return self.live_counts().get(login, 0) >= 1

    def moveto(self, login: str):
        """This login's moveto in its harness pane's foreground, with the
        pane's process info, or (None, info)."""
        pane = self.harness.get(login)
        if pane is None:
            return None, {}
        info = self.herdr.process_info(pane)
        foreground = [(p["pid"], p.get("argv") or []) for p in info.get("foreground_processes", [])
                      if isinstance(p.get("pid"), int)]
        return moveto_in(foreground, login), info

    def waiting(self, login: str) -> int | None:
        """The pid of this login's `moveto --wait` when its pane shows the prompt."""
        try:
            found, _ = self.moveto(login)
            if found is None or found.mode != WAIT:
                return None
            text = self.herdr.text("pane", "read", self.harness[login], "--source", "recent",
                                   "--lines", "5")
        except Exception:  # herdr busy or the pane gone: not waiting, asked again
            return None
        return found.pid if boot.at_prompt(text, login) else None

    def press(self, login: str) -> None:
        try:
            self.herdr.text("pane", "send-keys", self.harness[login], "enter")
        except Exception as error:  # said; the login then counts as not up after the tier's wait
            self.say(f"{login}: the Enter did not reach its pane ({boot.shown(str(error))})")

    def fleet(self) -> boot.Fleet:
        return boot.Fleet(up=self.up, waiting=self.waiting, press=self.press,
                          sleep=time.sleep, now=time.monotonic, say=self.say)


def probe_line(login: str | None) -> str | None:
    """None when the host's pinned sshd greets (or accounts are entered with
    sudo), otherwise the line that stops the boot."""
    try:
        pin = boot.ssh_pin(login) if login else None
    except boot.PinUnreadable as error:
        return f"{error}: sshd cannot be probed, so nothing was activated"
    if pin is None:
        return None
    why = boot.probe_sshd(*pin)
    if why is None:
        return None
    return (f"sshd at {pin[0]}:{pin[1]} refused this host's connection ({why}); its per-source "
            "penalty may hold for up to 10 minutes. Nothing was activated; run "
            "`fleet-deck start --auto` again once `ssh -p "
            f"{pin[1]} {pin[0]}` greets")


def fabric_ctl_has(op: str) -> bool:
    try:
        result = subprocess.run(["fabric-ctl", "--help"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return op in (result.stdout + result.stderr).split()


def control_agents(op: str, say: Callable[[str], None]) -> bool:
    """`fabric-ctl all control-start|control-stop`, once fabric-ctl has it."""
    if not fabric_ctl_has(op):
        say(f"control agents: fabric-ctl has no {op} yet; left as they are")
        return True
    result = subprocess.run(["fabric-ctl", "all", op], capture_output=True, text=True, timeout=300)
    for line in (result.stdout + result.stderr).splitlines():
        say(f"control agents: {boot.shown(line)}")
    return result.returncode == 0


def boot_fleet(say: Callable[[str], None], exclude: Iterable[str]) -> int:
    fleet = DeckFleet(say, exclude)
    fleet.await_tabs(TABS_READY_S)
    tiers = boot.plan_tiers(fleet.workspace)
    say("tiers: " + "; ".join(f"{tier} ({len(logins)})" for tier, logins in tiers))
    outcome = boot.activate(fleet.fleet(), tiers)
    say(f"up: {len(outcome.up)}; skipped: {', '.join(outcome.skipped) or 'none'}; "
        f"not up yet: {', '.join(outcome.late) or 'none'}")
    return 0 if not outcome.skipped and not outcome.late else 1


def stop_sessions(say: Callable[[str], None]) -> set[str]:
    """Every deck pane's session, in reverse boot order, tier by tier. The
    logins the deck has a harness pane for."""
    fleet = DeckFleet(say)
    try:
        fleet.read_map()
    except Exception as error:  # no map: herdr's stop below ends the panes anyway
        say(f"cannot read the deck's panes ({error}); herdr's stop ends them")
        return set()
    for tier, logins in reversed(boot.plan_tiers(fleet.workspace)):
        hung = []
        for login in logins:
            try:
                found, info = fleet.moveto(login)
            except Exception as error:  # one pane must not stop the rest; herdr's stop ends it
                say(f"{login}: cannot read its pane ({boot.shown(str(error))}); herdr's stop ends it")
                continue
            group = info.get("foreground_process_group_id")
            if found is not None and isinstance(group, int) and boot.hang_up(group):
                hung.append(login)
        if not hung:
            continue
        say(f"{tier}: ending {', '.join(hung)}")
        deadline = time.monotonic() + TIER_STOP_S
        while any(fleet.up(login) for login in hung) and time.monotonic() < deadline:
            time.sleep(boot.POLL_S)
    return set(fleet.harness)


def stop_all(say: Callable[[str], None]) -> int:
    """The reverse of a boot. The controller stops first although it is
    second in the boot's reverse: running, it would arm --wait again in each
    pane whose moveto ends."""
    ok = stop_controller(say)
    deck: set[str] = set()
    if server_up():
        deck = stop_sessions(say)
        subprocess.run([BIN, "server", "stop"], capture_output=True, text=True, timeout=60)
        if wait_for(lambda: server_up() is None, SERVER_STOP_S):
            say(f"{BIN}'s server stopped")
        else:
            say(f"{BIN}'s server did not stop within {SERVER_STOP_S}s")
            ok = False
    else:
        say(f"{BIN}'s server is not running")
    stop_holder(say)
    # Read before the control agents stop: they are what answers the state stream.
    live = {login for login, count in DeckFleet(say).live_counts().items() if count}
    ok = control_agents("control-stop", say) and ok
    if live & deck:
        say(f"the state stream still shows {', '.join(sorted(live & deck))} running; it can "
            "lag a session that just ended (fabric-ctl all presence answers from the hosts)")
    if live - deck:
        say(f"sessions outside the deck, left running: {', '.join(sorted(live - deck))}")
    return 0 if ok else 1


def confirm_stop_all(say: Callable[[str], None]) -> int:
    """The deck menu's Stop: asked in its popup, then run detached, since
    stopping herdr closes the popup it was asked in."""
    print("Stop the whole fleet: every agent's session, the deck controller, herdr\n"
          "(this popup closes with it) and the control agents.\n"
          "Type stop and press Enter to stop; anything else cancels.")
    try:
        answer = input("> ")
    except EOFError:
        answer = ""
    if answer.strip() != "stop":
        close_popup("Cancelled; nothing was stopped.")
        return 1
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    script = os.path.join(BOARD_DIR, "fleet-deck")
    spawn_detached([sys.executable, script, "stop", "--all"], log_path())
    close_popup(f"Stopping. Progress is written to {log_path()}.")
    return 0


def close_popup(line: str) -> None:
    """The popup's last word stays until a key: herdr may close it first."""
    print(line)
    try:
        input("Press Enter to close.")
    except EOFError:
        pass


def hold_lock_path() -> str:
    return os.path.join(state_dir(), "agent-hold.lock")


def hold_log_path() -> str:
    # Its own file: deck.log is rotated under it when a controller starts.
    return os.path.join(state_dir(), "agent-hold.log")


def stop_holder(say: Callable[[str], None]) -> None:
    holder = lock_holder(hold_lock_path())
    if holder is None or holder <= 0:  # 0: another pid namespace (stop_controller)
        return
    try:
        os.kill(holder, signal.SIGTERM)
    except ProcessLookupError:
        return
    if not wait_for(lambda: lock_holder(hold_lock_path()) is None, HOLD_STOP_S):
        say(f"the ssh-agent holder (pid {holder}) did not stop within {HOLD_STOP_S}s")


def ensure_link(agent: str, say: Callable[[str], None]) -> bool:
    """The running server's panes' agent link leads to a live agent: as it
    is, or once `fleet-deck hold-agent` has registered `agent` with it."""
    if boot.link_problem(herdr_socket_path()) is None:
        return True
    stop_holder(say)
    os.makedirs(state_dir(), mode=0o700, exist_ok=True)
    say(f"registering the ssh-agent at {agent} with {BIN}'s server (log: {hold_log_path()})")
    script = os.path.join(BOARD_DIR, "fleet-deck")
    rotate_log(hold_log_path())
    spawn_detached([sys.executable, script, "hold-agent", "--socket", agent], hold_log_path())
    if wait_for(lambda: boot.link_problem(herdr_socket_path()) is None, HOLD_READY_S):
        say("panes' ssh-agent: live")
        return True
    say(boot.link_problem(herdr_socket_path()) or "panes' ssh-agent: not live; the log says why")
    stop_holder(say)  # a registration that did not mend the link is not kept running
    return False


def hold_agent(agent: str) -> int:
    """`fleet-deck hold-agent`: hold the registration until SIGTERM."""
    import threading

    def log(line: str) -> None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z ")
        print(f"{stamp}fleet-deck hold-agent: {line}", file=sys.stderr, flush=True)

    if hold_lock(hold_lock_path()) is None:
        log("another holder runs on this login; this one stops")
        return 1
    stopped = threading.Event()
    hold = boot.AgentHold(agent, herdr_socket_path, log)

    def stop(_signum, _frame):
        stopped.set()
        hold.close()

    signal.signal(signal.SIGTERM, stop)
    hold.run(sleep=stopped.wait)
    return 0


def start(args, say: Callable[[str], None]) -> int:
    line, checked = prefix_line(herdr_config_path())
    if not checked:
        say(f"{line}: not the prefix checked against Claude Code, Codex and the shell; "
            "remove keys.prefix to use ctrl+6")
    server = server_up()
    controller = lock_holder(lock_path())
    problem = boot.link_problem(herdr_socket_path()) if server else None
    if problem:
        say(problem)
    starting = server is None or controller is None or args.verb == "restart"
    agent = None
    if starting or args.auto:
        agent = boot.ensure_agent(say, interactive=sys.stdin.isatty(),
                                  first=boot.link_target(herdr_socket_path()) if server else None)
        if agent is None:
            return 1
    elif problem:
        say("attaching as before; `fleet-deck restart` mends the panes' ssh-agent")
    if args.auto:
        # Once per boot, before the first pane is activated.
        try:
            first = next(iter(parse_moveto_list(moveto_list(), {getpass.getuser()})), None)
        except (OSError, subprocess.SubprocessError):
            first = None
        line = probe_line(first.login if first else None)
        if line:
            say(line)
            return 1
    if args.verb == "restart" and not stop_controller(say):
        return 1
    if not ensure_server(say, agent):
        return 1
    if agent is not None and not ensure_link(agent, say):
        return 1
    if not ensure_controller(args, say, agent):
        return 1
    if args.auto:
        if not control_agents("control-start", say):
            say("some control agents did not start; going on with the panes")
        return boot_fleet(say, args.exclude)
    if args.verb == "attach":
        return attach()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="fleet-deck",
        description="Fleet Deck in one command: herdr's server, the deck controller "
        "(detached) and this terminal attached. A second run only attaches.",
        epilog="stop and restart act on the deck controller only; herdr's server keeps "
        "every agent's pane running (herdr server stop would end them). stop --all ends "
        "everything, sessions included.",
    )
    parser.add_argument(
        "verb", nargs="?", default="attach",
        choices=["attach", "start", "stop", "restart", "status", "hold-agent"],
        help="attach (default): start what is missing, then attach this terminal; "
        "start: the same without attaching; stop|restart: the controller; "
        "status: what runs (exit 0 when both run, 3 otherwise); "
        "hold-agent: started by start itself",
    )
    parser.add_argument("--socket", help=argparse.SUPPRESS)
    parser.add_argument("--auto", action="store_true",
                        help="start only: then activate every agent, tier by tier, no Enter typed")
    parser.add_argument("--all", action="store_true",
                        help="stop only: every session, the controller, herdr and the control agents")
    parser.add_argument("--confirm", action="store_true",
                        help="with stop --all: ask first, then stop detached (the deck menu's Stop)")
    parser.add_argument("--catalog", help="the role catalogue (default: the agent-fabric checkout's)")
    parser.add_argument("--exclude", action="append", default=[], help="a login to leave out")
    parser.add_argument("--cwd", help="the deck's working directory for new tabs")
    parser.add_argument("--no-fleet-tab", action="store_true",
                        help="do not open the fleet board as a tab of its own")
    args = parser.parse_args(argv)
    if args.auto and args.verb != "start":
        parser.error("--auto goes with start")
    if args.all and args.verb != "stop":
        parser.error("--all goes with stop")
    if args.confirm and not args.all:
        parser.error("--confirm goes with stop --all")

    def say(line: str) -> None:
        print(f"fleet-deck: {line}", file=sys.stderr, flush=True)

    if args.verb == "status":
        return status(say)
    if args.verb == "hold-agent":
        if not args.socket:
            parser.error("hold-agent needs --socket")
        return hold_agent(args.socket)
    if in_herdr_pane() and (args.verb != "stop" or args.all):
        # server.socket_access = "outside_panes" refuses a pane's process, a
        # controller started here would be the pane's descendant, and stop
        # --all would end the pane it runs in half-way.
        say("run this from a terminal outside herdr's panes")
        return 2
    if args.verb == "stop" and args.confirm:
        # A popup is not a pane here (in_herdr_pane): the deck menu asks from one.
        return confirm_stop_all(say)
    if args.verb == "stop":
        if args.all:
            return stop_all(say)
        return 0 if stop_controller(say) else 1
    return start(args, say)


if __name__ == "__main__":
    raise SystemExit(main())
