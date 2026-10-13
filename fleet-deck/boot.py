"""The fleet's boot and stop, for `fleet-deck start --auto` and `stop --all`.

Booting has to hold one rule above the others: no herdr server and no pane
is started without a live ssh-agent holding the operator's deck key. herdr
gives every pane `SSH_AUTH_SOCK=<api socket>.agent`, a link the server
points at the agent it inherited, else at one a client registered
(`server.ssh_agent.register`), else at `<api socket>.unavailable`
(src/platform/ssh_agent.rs). A server started from a terminal with no
agent therefore gives every pane a dead agent, and each pane's `ssh`
falls back to the key file and asks for its passphrase: 23 prompts on
2026-10-13. A local attach registers nothing, so attaching later never
mends it; a registration held by `fleet-deck hold-agent` (AgentHold) does.
herdr drops a registration when its connection closes (upstream's rule:
an attachment's agent is not used after it detaches), so the holder is a
process of its own, not the deck controller: stopping or restarting the
controller must not take the panes' agent with it.

Activation presses the one Enter that `moveto <login> --wait` asks for,
and only when the pane's foreground is that login's `moveto --wait` and
its last line is moveto's own "<login> - Enter to activate": a pane at a
passphrase prompt, a shell or a harness is never typed into.

The policies are pure and take their effects injected, so their order,
pacing and refusals are tested without a fleet.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable

# The tiers, in boot order, as the deck's workspaces are labelled (agent-fabric
# identities/roles/catalog.json groups). Every "<language> Developer"
# workspace is one tier; any other workspace (New, one the operator made) is
# activated last.
COORDINATOR = "Coordinator"
DEVELOPERS = "Developers"
OTHER = "Other"
TIERS = (COORDINATOR, "C-Level", "Infrastructure", "Experts", DEVELOPERS, OTHER)

# Within a tier one login at a time, this far apart: each activation pulls
# the account's checkout and starts a harness, and the host's sshd penalises
# a burst from one source.
PRESS_GAP_S = 4.0
# The next tier starts when every login of this one is up, or this long
# after its last press.
TIER_WAIT_S = 60.0
# How long a pane has to show moveto's prompt before the attempt fails: a
# freshly started controller first waits for the restore decision.
PROMPT_WAIT_S = 45.0
# A login whose moveto fails this many times is reported and skipped.
ATTEMPTS = 2
POLL_S = 2.0

DECK_KEY = "~/.ssh/fabric_deck"


def tier_of(workspace: str | None) -> str:
    if workspace in TIERS[:4]:
        return workspace
    if workspace and (workspace == DEVELOPERS or workspace.endswith(" Developer")):
        return DEVELOPERS
    return OTHER


def plan_tiers(workspaces: dict[str, str | None]) -> list[tuple[str, list[str]]]:
    """Logins grouped by tier in boot order, each tier's logins sorted; a
    tier with no login is left out. `workspaces` maps a login to the label
    of the workspace its tab is in."""
    grouped: dict[str, list[str]] = {}
    for login, label in workspaces.items():
        grouped.setdefault(tier_of(label), []).append(login)
    return [(tier, sorted(grouped[tier])) for tier in TIERS if tier in grouped]


def prompt_line(login: str) -> str:
    """The line `moveto <login> --wait` prints and then waits on
    (agent-fabric runtime/provisioning/moveto/moveto.py)."""
    return f"{login} - Enter to activate"


def at_prompt(text: str, login: str) -> bool:
    """Whether a pane's recent output ends with moveto's prompt for this
    login: its last non-blank line, exactly, so a prompt scrolled up by a
    passphrase question or a shell does not count."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return bool(lines) and lines[-1] == prompt_line(login)


# ------------------------------------------------------------ activation


@dataclass
class Fleet:
    """What activation needs of the deck, injected: whether a login's
    session is up; the pid of the `moveto --wait` its harness pane waits on
    at moveto's prompt, or None; the press; the clock and the terminal."""

    up: Callable[[str], bool]
    waiting: Callable[[str], int | None]
    press: Callable[[str], None]
    sleep: Callable[[float], None]
    now: Callable[[], float]
    say: Callable[[str], None]


@dataclass
class Outcome:
    up: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    late: list[str] = field(default_factory=list)


@dataclass
class _Run:
    """One activation: every press, re-presses included, is PRESS_GAP_S
    after the one before."""

    fleet: Fleet
    outcome: Outcome = field(default_factory=Outcome)
    attempts: dict[str, int] = field(default_factory=dict)
    # login -> the pid of the moveto that was pressed
    pressed_pid: dict[str, int] = field(default_factory=dict)
    last_press: float | None = None

    def press(self, login: str, pid: int) -> None:
        if self.last_press is not None:
            gap = self.last_press + PRESS_GAP_S - self.fleet.now()
            if gap > 0:
                self.fleet.sleep(gap)
        self.fleet.press(login)
        self.last_press = self.fleet.now()
        self.pressed_pid[login] = pid
        self.attempts[login] = self.attempts.get(login, 0) + 1


def activate(fleet: Fleet, tiers: list[tuple[str, list[str]]]) -> Outcome:
    """Activate every login that is not up, tier by tier. The Coordinator
    tier is never activated: it is up before the deck boots the fleet, and a
    dormant coordinator pane is the operator's own call."""
    run = _Run(fleet)
    for tier, logins in tiers:
        if tier == COORDINATOR:
            fleet.say(f"{tier}: not activated (the coordinator is up before the boot)")
            continue
        pressed: list[str] = []
        for login in logins:
            if fleet.up(login):
                run.outcome.up.append(login)
                continue
            if _press_when_waiting(run, login):
                pressed.append(login)
            else:
                fleet.say(f"{login}: its pane never showed moveto's prompt; skipped")
                run.outcome.skipped.append(login)
        _await_tier(run, tier, pressed)
    return run.outcome


def _press_when_waiting(run: _Run, login: str) -> bool:
    fleet = run.fleet
    deadline = fleet.now() + PROMPT_WAIT_S
    while True:
        pid = fleet.waiting(login)
        if pid is not None:
            run.press(login, pid)
            fleet.say(f"{login}: activated")
            return True
        if fleet.now() >= deadline:
            return False
        fleet.sleep(POLL_S)


def _await_tier(run: _Run, tier: str, pressed: list[str]) -> None:
    """Wait until every pressed login is up, or TIER_WAIT_S after the last
    press. The prompt stays on screen after a press while moveto refreshes
    the account (it prints nothing then), so a prompt alone says nothing:
    only another moveto at the prompt (the pressed one ended and the deck
    armed --wait again) is a failure, pressed once more, then given up."""
    fleet = run.fleet
    waiting = list(pressed)
    while waiting:
        for login in list(waiting):
            if fleet.up(login):
                waiting.remove(login)
                run.outcome.up.append(login)
                continue
            pid = fleet.waiting(login)
            if pid is None or pid == run.pressed_pid[login]:
                continue
            if run.attempts[login] >= ATTEMPTS:
                fleet.say(f"{login}: moveto ended before a session came up, "
                          f"{run.attempts[login]} times; skipped")
                waiting.remove(login)
                run.outcome.skipped.append(login)
            else:
                run.press(login, pid)
                fleet.say(f"{login}: moveto ended before a session came up; activated again")
        if not waiting:
            break
        if fleet.now() >= (run.last_press or 0.0) + TIER_WAIT_S:
            fleet.say(f"{tier}: {', '.join(waiting)} not up after {TIER_WAIT_S:.0f}s; "
                      "going on to the next tier")
            run.outcome.late.extend(waiting)
            break
        fleet.sleep(POLL_S)


# ---------------------------------------------------------- the ssh-agent


Run = Callable[..., subprocess.CompletedProcess]


def key_fingerprint(key: str, run: Run = subprocess.run) -> str | None:
    """The deck key's SHA256 fingerprint, from its .pub, else from the key
    file itself (an OpenSSH private key keeps its public half unencrypted,
    so no passphrase is asked)."""
    path = os.path.expanduser(key)
    for candidate in (path + ".pub", path):
        if not os.path.exists(candidate):
            continue
        result = run(["ssh-keygen", "-l", "-f", candidate], capture_output=True, text=True,
                     timeout=10, stdin=subprocess.DEVNULL)
        fields = result.stdout.split()
        if result.returncode == 0 and len(fields) >= 2:
            return fields[1]
    return None


HOLDS, LIVE, DEAD = "holds", "live", "dead"


def agent_state(sock: str, fingerprint: str, run: Run = subprocess.run) -> str:
    """HOLDS when the agent at `sock` lists the fingerprint, LIVE when it
    answers without it, DEAD when nothing answers there. ssh-add -l exits 1
    for an agent with no identity and 2 when it cannot reach one."""
    if not sock or not os.path.exists(sock):
        return DEAD
    env = dict(os.environ, SSH_AUTH_SOCK=sock)
    try:
        result = run(["ssh-add", "-l"], capture_output=True, text=True, timeout=10,
                     env=env, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return DEAD
    if result.returncode == 0 and fingerprint in result.stdout.split():
        return HOLDS
    return LIVE if result.returncode in (0, 1) else DEAD


def own_agent_path(env: dict[str, str] | None = None) -> str:
    """Where the deck starts an ssh-agent of its own when the login has none."""
    env = os.environ if env is None else env
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(runtime, "fabric-deck", "agent.sock")


def agent_candidates(env: dict[str, str] | None = None, first: str | None = None) -> list[str]:
    """The agent sockets tried, in order: `first` (the agent a running
    server already gives its panes), this terminal's, the desktop keyring's
    (in the runtime directory, so a test's own directory never reaches the
    operator's), then the deck's own."""
    env = os.environ if env is None else env
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    seen: list[str] = []
    for path in (first or "", env.get("SSH_AUTH_SOCK", ""), os.path.join(runtime, "keyring", ".ssh"),
                 own_agent_path(env)):
        if path and path not in seen:
            seen.append(path)
    return seen


def find_agent(fingerprint: str, candidates: Iterable[str], run: Run = subprocess.run) -> str | None:
    return next((s for s in candidates if agent_state(s, fingerprint, run) == HOLDS), None)


def ensure_agent(say: Callable[[str], None], interactive: bool, key: str = DECK_KEY,
                 env: dict[str, str] | None = None, run: Run = subprocess.run,
                 first: str | None = None) -> str | None:
    """The socket of a live agent holding the deck key. Without one, the key
    is added once, here, to the first live agent (an ssh-agent of the deck's
    own is started when none is live), and the operator types its
    passphrase in this terminal. None, said, when that cannot be. `first`
    is tried before the others: herdr prefers the agent its server
    inherited over any registered one, so a live inherited agent without
    the key gets the key, not a rival."""
    fingerprint = key_fingerprint(key, run)
    if fingerprint is None:
        say(f"no deck key at {key} (its .pub or the key itself): nothing is started")
        return None
    candidates = agent_candidates(env, first)
    # A live `first` is the agent herdr's panes use whatever else is registered:
    # only the key in it helps, so no other agent is looked for.
    first_live = first is not None and agent_state(first, fingerprint, run) != DEAD
    found = find_agent(fingerprint, [first] if first_live else candidates, run)
    if found:
        return found
    if not interactive:
        say(f"no ssh-agent holds {key}, and this is no terminal to type its passphrase in: "
            "nothing is started")
        return None
    target = first if first_live else next(
        (s for s in candidates if agent_state(s, fingerprint, run) == LIVE), None)
    if target is None:
        target = own_agent_path(env)
        os.makedirs(os.path.dirname(target), mode=0o700, exist_ok=True)
        if os.path.lexists(target):
            os.unlink(target)  # a dead agent's socket: ssh-agent -a refuses an existing path
        say(f"no ssh-agent answers; starting one at {target}")
        started = run(["ssh-agent", "-a", target], capture_output=True, text=True, timeout=10,
                      stdin=subprocess.DEVNULL)
        if started.returncode != 0:
            say(f"ssh-agent did not start: {(started.stderr or started.stdout).strip()[:200]}")
            return None
    say(f"adding {key} to the ssh-agent at {target}: type its passphrase once")
    # The terminal's own stdin and stderr: ssh-add asks the operator directly.
    run(["ssh-add", os.path.expanduser(key)], env=dict(os.environ, SSH_AUTH_SOCK=target))
    if agent_state(target, fingerprint, run) == HOLDS:
        return target
    say(f"the ssh-agent at {target} still does not hold {key}: nothing is started")
    return None


# ----------------------------------------------------------- the pane link


def agent_link(api_socket: str | None) -> str | None:
    """The link herdr gives every pane as SSH_AUTH_SOCK (<api socket>.agent)."""
    return api_socket + ".agent" if api_socket else None


def socket_answers(path: str) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(path)
        return True
    except OSError:
        return False


def link_target(api_socket: str | None) -> str | None:
    link = agent_link(api_socket)
    try:
        return os.readlink(link) if link else None
    except OSError:
        return None


def link_problem(api_socket: str | None, key: str | None = DECK_KEY,
                 run: Run = subprocess.run) -> str | None:
    """What is wrong with the panes' agent link of a running server, or None
    when it leads to an agent that answers and, with `key`, holds that key."""
    link = agent_link(api_socket)
    if link is None:
        return None
    try:
        target = os.readlink(link)
    except FileNotFoundError:
        return (f"herdr's server gives its panes no ssh-agent ({link} is missing): panes it "
                "made before now ask for the key's passphrase; restart it with "
                "`fleet-deck stop --all` and `fleet-deck start --auto`")
    except OSError as error:
        return f"cannot read {link}: {error.strerror}"
    if target.endswith(".unavailable") or not socket_answers(link):
        return f"herdr's panes' ssh-agent link {link} leads to no live agent ({target})"
    fingerprint = key_fingerprint(key, run) if key else None
    if fingerprint and agent_state(link, fingerprint, run) != HOLDS:
        return f"the ssh-agent herdr's panes use ({target}) does not hold {key}"
    return None


# --------------------------------------------------------- the registration

HOLD_RETRY_S = (2, 5, 30)


def register_request(agent: str) -> bytes:
    return (json.dumps({"id": "fleet-deck:ssh-agent", "method": "server.ssh_agent.register",
                        "params": {"socket_path": agent}}) + "\n").encode()


def read_line(sock: socket.socket, limit: int = 4096) -> bytes:
    line = b""
    while not line.endswith(b"\n") and len(line) < limit:
        chunk = sock.recv(1)
        if not chunk:
            break
        line += chunk
    return line


def shown(text: str) -> str:
    """A server's answer, safe to print on the operator's terminal."""
    return "".join(ch for ch in text if ch.isprintable())[:200]


@dataclass
class AgentHold:
    """The operator's ssh-agent registered with herdr's server
    (`server.ssh_agent.register`) and held: the registration lasts as long
    as this connection, and is made again when a server ends it (stopped,
    or replaced by a new one). The link itself is the server's; nothing
    here touches it."""

    agent: str
    api_socket: Callable[[], str | None]
    log: Callable[[str], None]
    closing: bool = False
    sock: socket.socket | None = None

    def hold_once(self) -> str | None:
        """Register, then block until the server ends the connection. None
        when a registration was taken and ended; otherwise why it was not
        taken."""
        path = self.api_socket()
        if not path:
            return "herdr's server socket is unknown"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                self.sock = sock
                sock.settimeout(10)
                sock.connect(path)
                sock.sendall(register_request(self.agent))
                try:
                    reply = json.loads(read_line(sock))
                except ValueError:
                    return "herdr's server did not answer the registration"
                if not isinstance(reply, dict) or "result" not in reply:
                    error = reply.get("error") if isinstance(reply, dict) else None
                    detail = error.get("message") if isinstance(error, dict) else reply
                    return f"herdr refused the ssh-agent: {shown(str(detail))}"
                self.log(f"herdr's panes use the ssh-agent at {self.agent}")
                sock.settimeout(None)
                while sock.recv(64):
                    pass
            return None
        except OSError as error:
            return f"cannot reach herdr's server: {error.strerror or error}"
        finally:
            self.sock = None

    def run(self, sleep: Callable[[float], None] = time.sleep) -> None:
        refused = 0
        said = None
        while not self.closing:
            why = self.hold_once()
            if self.closing:
                return
            if why is None:
                refused, said = 0, None
                self.log("herdr's server let the ssh-agent registration go; registering again")
            else:
                if why != said:
                    self.log(f"{why}; trying again")
                    said = why
                refused += 1
            sleep(HOLD_RETRY_S[min(refused, len(HOLD_RETRY_S) - 1)])

    def close(self) -> None:
        self.closing = True
        sock = self.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


# --------------------------------------------------------- the sshd probe


class PinUnreadable(RuntimeError):
    pass


def ssh_pin(login: str, run: Run = subprocess.run) -> tuple[str, int] | None:
    """The host's pinned sshd as moveto reads it (`fabric-host ssh-pin`), or
    None when the account is entered with sudo. A pin that cannot be read
    raises PinUnreadable, as moveto refuses then."""
    try:
        result = run(["fabric-host", "ssh-pin", login], capture_output=True, text=True,
                     timeout=30, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PinUnreadable(f"cannot run fabric-host ssh-pin ({error.__class__.__name__})") from None
    words = result.stdout.split()
    if result.returncode == 0 and words == ["sudo"]:
        return None
    if result.returncode == 0 and len(words) == 3 and words[0] == "ssh" and words[2].isdigit():
        return words[1], int(words[2])
    why = shown((result.stderr.strip().splitlines() or [f"exit {result.returncode}"])[-1])
    raise PinUnreadable(f"fabric-host ssh-pin {login} gave no pin ({why})")


def probe_sshd(address: str, port: int, timeout: float = 5.0) -> str | None:
    """None when sshd at address:port greets with its banner; otherwise why
    not. Only the banner is read, so the probe never authenticates: sshd's
    per-source penalty counts it as one unauthenticated connection, and the
    probe runs once per boot."""
    try:
        with socket.create_connection((address, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            banner = b""
            while b"\n" not in banner and len(banner) < 256:
                chunk = sock.recv(256)
                if not chunk:
                    break
                banner += chunk
    except OSError as error:
        return error.strerror or str(error)
    if banner.startswith(b"SSH-"):
        return None
    return "it closed the connection without a greeting" if not banner else "it did not greet as sshd"


# ------------------------------------------------------------ stopping


def hang_up(pgid: int) -> bool:
    """End a pane's moveto (and the session it carries) as closing the pane
    would: SIGHUP to its foreground group."""
    if pgid <= 1:
        return False
    try:
        os.killpg(pgid, signal.SIGHUP)
    except (ProcessLookupError, PermissionError):
        return False
    return True
