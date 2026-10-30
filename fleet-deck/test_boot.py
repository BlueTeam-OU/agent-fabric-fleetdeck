"""boot.py: the tier order, the pacing, the ssh-agent and its pane link, the
sshd probe. The activation runs on a simulated clock; the agent tests run
the host's own ssh-keygen, ssh-agent and ssh-add on a throwaway key."""

import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

import base64
import struct

import boot
from boot import COORDINATOR, DEVELOPERS, OTHER, Fleet


class TiersTest(unittest.TestCase):
    def test_workspaces_map_to_tiers_in_boot_order(self):
        workspaces = {
            "dev-b": "Rust Developer", "dev-a": "Python Developer", "ops": "Infrastructure",
            "cto": "C-Level", "lang": "Experts", "lost": "New", "coord": "Coordinator",
            "nowhere": None,
        }
        self.assertEqual(boot.plan_tiers(workspaces), [
            (COORDINATOR, ["coord"]),
            ("C-Level", ["cto"]),
            ("Infrastructure", ["ops"]),
            ("Experts", ["lang"]),
            (DEVELOPERS, ["dev-a", "dev-b"]),
            (OTHER, ["lost", "nowhere"]),
        ])

    def test_marketing_legal_and_accountants_boot_with_experts(self):
        workspaces = {
            "dev": "Rust Developer", "brand": "Marketing", "legal": "Legal", "books": "Accountants",
            "lang": "Experts", "ops": "Infrastructure", "cto": "C-Level",
        }
        self.assertEqual(boot.plan_tiers(workspaces), [
            ("C-Level", ["cto"]),
            ("Infrastructure", ["ops"]),
            ("Experts", ["books", "brand", "lang", "legal"]),
            (DEVELOPERS, ["dev"]),
        ])

    def test_the_coordinator_role_is_the_coordinator_tier_wherever_its_tab_is(self):
        workspaces = {"coord": "C-Level", "cto": "C-Level", "ops": "Infrastructure"}
        roles = {"coord": boot.COORDINATOR_ROLE, "cto": "architect-cto", "ops": "devex-tooling"}
        self.assertEqual(boot.plan_tiers(workspaces, roles), [
            (COORDINATOR, ["coord"]),
            ("C-Level", ["cto"]),
            ("Infrastructure", ["ops"]),
        ])

    def test_a_coordinator_in_c_level_is_never_pressed(self):
        tiers = boot.plan_tiers({"coord": "C-Level", "cto": "C-Level"},
                                {"coord": boot.COORDINATOR_ROLE, "cto": "architect-cto"})
        sim = Sim(prompt_at={"coord": 0.0, "cto": 0.0})
        boot.activate(sim.fleet(), tiers)
        pressed = [login for _, login in sim.presses]
        self.assertEqual(pressed, ["cto"])

    def test_an_unbound_role_keeps_its_workspace_tier(self):
        self.assertEqual(boot.plan_tiers({"a": "Legal"}, {"a": "-"}), [("Experts", ["a"])])

    def test_an_empty_tier_is_left_out(self):
        self.assertEqual(boot.plan_tiers({"a": "Experts"}), [("Experts", ["a"])])

    def test_only_the_last_line_is_the_prompt(self):
        self.assertTrue(boot.at_prompt("moveto: x over ssh\nx - Enter to activate\n\n", "x"))
        self.assertFalse(boot.at_prompt("x - Enter to activate\nEnter passphrase for key:", "x"))
        self.assertFalse(boot.at_prompt("y - Enter to activate\n", "x"), "another login's prompt")
        self.assertFalse(boot.at_prompt("", "x"))


class Sim:
    """A fleet on a simulated clock, as a real pane behaves: `prompt_at`
    is when a login's pane first shows moveto's prompt; after a press the
    prompt stays on screen (moveto refreshes the account silently) until
    the session is up, `up_after` seconds later. A login in `fails` has its
    moveto end that many times, `fail_after` seconds after a press; the
    deck then arms a new moveto --wait (another pid) at once."""

    def __init__(self, prompt_at=None, up_after=10.0, already_up=(), fails=None, never_up=(),
                 fail_after=5.0):
        self.t = 0.0
        self.prompt_at = prompt_at or {}
        self.up_after = up_after
        self.up_at = {login: 0.0 for login in already_up}
        self.fails = dict(fails or {})
        self.fail_after = fail_after
        self.never_up = set(never_up)
        self.presses: list[tuple[float, str]] = []
        self.lines: list[str] = []
        self.pid: dict[str, int] = {}
        self.rearm: dict[str, float] = {}
        self.next_pid = 100
        self.done: list[str] = []

    def fleet(self):
        return Fleet(up=self.up, waiting=self.waiting, press=self.press, sleep=self.sleep,
                     now=lambda: self.t, say=self.lines.append, done=self.done.append)

    def up(self, login):
        return login in self.up_at and self.t >= self.up_at[login]

    def waiting(self, login):
        if self.up(login) or self.t < self.prompt_at.get(login, 0.0):
            return None
        if login in self.rearm and self.t >= self.rearm[login]:
            del self.rearm[login]
            self.pid.pop(login, None)
        if login not in self.pid:
            self.next_pid += 1
            self.pid[login] = self.next_pid
        return self.pid[login]

    def press(self, login):
        assert self.waiting(login) is not None, f"{login} pressed while not at its prompt"
        assert login not in self.rearm, f"{login} pressed again while its moveto still runs"
        self.presses.append((self.t, login))
        if self.fails.get(login, 0) > 0:
            self.fails[login] -= 1
            self.rearm[login] = self.t + self.fail_after
        elif login not in self.never_up:
            self.up_at[login] = self.t + self.up_after

    def sleep(self, seconds):
        self.t += seconds


class ActivationTest(unittest.TestCase):
    def test_only_a_login_seen_up_after_its_activation_is_done(self):
        # done ends the attach the boot opened: never for a login it did not
        # reach, nor for one that did not come up, whose pane shows why.
        sim = Sim(already_up={"a"}, never_up={"slow"}, prompt_at={"late": 1e9})
        tiers = [(DEVELOPERS, ["a", "b", "slow", "late"])]
        boot.activate(sim.fleet(), tiers)
        self.assertEqual(sim.done, ["b"])

    def test_tier_order_and_four_seconds_between_presses(self):
        sim = Sim()
        tiers = [(COORDINATOR, ["user"]), ("C-Level", ["a", "b"]), (DEVELOPERS, ["c", "d", "e"])]
        outcome = boot.activate(sim.fleet(), tiers)
        order = [login for _, login in sim.presses]
        self.assertEqual(order, ["a", "b", "c", "d", "e"], "the coordinator is never pressed")
        times = dict((login, t) for t, login in sim.presses)
        self.assertEqual(times["b"] - times["a"], 4.0, "the owner asked for 4 s")
        self.assertEqual(times["d"] - times["c"], 4.0)
        self.assertEqual(times["e"] - times["d"], 4.0)
        # The next tier waits for this one to be up.
        self.assertGreaterEqual(times["c"], times["b"] + sim.up_after)
        self.assertEqual(sorted(outcome.up), ["a", "b", "c", "d", "e"])
        self.assertEqual(outcome.skipped, [])

    def test_the_next_tier_starts_after_sixty_seconds_without_the_last(self):
        sim = Sim(never_up={"slow"})
        outcome = boot.activate(sim.fleet(), [("C-Level", ["slow"]), ("Experts", ["x"])])
        times = dict((login, t) for t, login in sim.presses)
        self.assertGreaterEqual(times["x"] - times["slow"], 60.0, "the owner asked for 60 s")
        self.assertLess(times["x"] - times["slow"], 60.0 + boot.POLL_S + 0.001)
        self.assertEqual(outcome.late, ["slow"])
        self.assertIn("x", outcome.up)

    def test_a_login_already_up_is_not_pressed(self):
        sim = Sim(already_up={"a"})
        outcome = boot.activate(sim.fleet(), [("Experts", ["a", "b"])])
        self.assertEqual([login for _, login in sim.presses], ["b"])
        self.assertEqual(sorted(outcome.up), ["a", "b"])

    def test_no_press_before_the_prompt_shows(self):
        sim = Sim(prompt_at={"a": 13.0})
        boot.activate(sim.fleet(), [("Experts", ["a"])])
        self.assertGreaterEqual(sim.presses[0][0], 13.0)

    def test_a_pane_that_never_prompts_is_skipped_and_the_rest_go_on(self):
        sim = Sim(prompt_at={"stuck": 10_000.0})
        outcome = boot.activate(sim.fleet(), [("Experts", ["stuck", "b"])])
        self.assertEqual([login for _, login in sim.presses], ["b"])
        self.assertEqual(outcome.skipped, ["stuck"])
        self.assertTrue(any("stuck" in line and "skipped" in line for line in sim.lines))

    def test_a_prompt_left_on_screen_during_the_refresh_is_not_pressed_again(self):
        # moveto prints nothing while it refreshes the account after Enter.
        sim = Sim(up_after=50.0)
        outcome = boot.activate(sim.fleet(), [("Experts", ["a", "b"])])
        self.assertEqual([login for _, login in sim.presses], ["a", "b"])
        self.assertEqual(sorted(outcome.up), ["a", "b"])
        self.assertEqual(outcome.skipped, [])

    def test_a_login_activated_during_the_gap_is_not_pressed(self):
        # A person presses b's Enter while the deck waits out the gap after a.
        sim = Sim(up_after=30.0)
        sim.up_at["b"] = 2.0
        outcome = boot.activate(sim.fleet(), [("Experts", ["a", "b"])])
        self.assertEqual([login for _, login in sim.presses], ["a"])
        self.assertEqual(sorted(outcome.up), ["a", "b"])
        self.assertEqual(outcome.skipped, [])

    def test_every_press_keeps_the_gap_re_presses_included(self):
        sim = Sim(fails={"a": 1, "b": 1}, fail_after=0.5)
        boot.activate(sim.fleet(), [("Experts", ["a", "b"])])
        times = [t for t, _ in sim.presses]
        self.assertEqual(len(times), 4)
        self.assertTrue(all(b - a >= 4.0 for a, b in zip(times, times[1:])), sim.presses)

    def test_a_moveto_that_ends_once_is_pressed_again(self):
        sim = Sim(fails={"a": 1})
        outcome = boot.activate(sim.fleet(), [("Experts", ["a"])])
        self.assertEqual([login for _, login in sim.presses], ["a", "a"])
        self.assertEqual(outcome.up, ["a"])

    def test_a_moveto_that_fails_twice_is_reported_and_skipped(self):
        sim = Sim(fails={"a": 5})
        outcome = boot.activate(sim.fleet(), [("Experts", ["a", "b"]), (DEVELOPERS, ["c"])])
        self.assertEqual([login for _, login in sim.presses].count("a"), boot.ATTEMPTS)
        self.assertEqual(outcome.skipped, ["a"])
        self.assertEqual(sorted(outcome.up), ["b", "c"])
        self.assertTrue(any(line.startswith("a: moveto ended") and "skipped" in line
                            for line in sim.lines), sim.lines)


class ListingOnlyAgent:
    """An agent that lists a key it cannot sign with, as the desktop keyring's
    proxy does with every key in ~/.ssh: identities are answered with the
    key, everything else (a signature, an added key) with a failure."""

    IDENTITIES, ANSWER, SIGN, FAILURE = 11, 12, 13, 5

    def __init__(self, path: str, pub: str):
        with open(pub) as public:
            blob = base64.b64decode(public.read().split()[1])
        self.answer = (bytes([self.ANSWER]) + struct.pack(">I", 1)
                       + struct.pack(">I", len(blob)) + blob + struct.pack(">I", 4) + b"pub!")
        self.asked = 0  # signatures asked for
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(path)
        self.listener.listen(8)
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self.talk, args=(conn,), daemon=True).start()

    def talk(self, conn):
        with conn:
            while True:
                head = conn.recv(4, socket.MSG_WAITALL)
                if len(head) < 4:
                    return
                body = conn.recv(struct.unpack(">I", head)[0], socket.MSG_WAITALL)
                listing = body[:1] == bytes([self.IDENTITIES])
                self.asked += body[:1] == bytes([self.SIGN])
                reply = self.answer if listing else bytes([self.FAILURE])
                conn.sendall(struct.pack(">I", len(reply)) + reply)

    def close(self):
        self.listener.close()


class AgentTest(unittest.TestCase):
    """The host's own ssh tools on a throwaway key and agent."""

    @classmethod
    def setUpClass(cls):
        if not all(shutil.which(t) for t in ("ssh-keygen", "ssh-agent", "ssh-add")):
            raise unittest.SkipTest("no OpenSSH client tools on this host")

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="boot-agent-")
        runtime = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self.sock_dir = tempfile.mkdtemp(prefix="ba-", dir=runtime)
        self.key = os.path.join(self.dir, "fabric_deck")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", self.key],
                       check=True, stdin=subprocess.DEVNULL)
        self.agents: list[int] = []
        self.addCleanup(self.clean)

    def clean(self):
        for pid in self.agents:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.rmtree(self.sock_dir, ignore_errors=True)

    def start_agent(self, name="agent") -> str:
        path = os.path.join(self.sock_dir, name)
        out = subprocess.run(["ssh-agent", "-a", path, "-s"], capture_output=True, text=True,
                             check=True, stdin=subprocess.DEVNULL).stdout
        self.agents.append(int(out.split("SSH_AGENT_PID=")[1].split(";")[0]))
        return path

    def add_key(self, sock):
        subprocess.run(["ssh-add", "-q", self.key], env=dict(os.environ, SSH_AUTH_SOCK=sock),
                       check=True, capture_output=True, stdin=subprocess.DEVNULL)

    def test_the_agent_holding_the_key_is_found_past_one_that_does_not(self):
        empty, holding = self.start_agent("empty"), self.start_agent("holding")
        self.add_key(holding)
        fingerprint = boot.key_fingerprint(self.key)
        self.assertTrue(fingerprint and fingerprint.startswith("SHA256:"))
        dead = os.path.join(self.sock_dir, "dead")
        self.assertEqual(boot.agent_state(dead, self.key, fingerprint), boot.DEAD)
        self.assertEqual(boot.agent_state(empty, self.key, fingerprint), boot.LIVE)
        self.assertEqual(boot.agent_state(holding, self.key, fingerprint), boot.HOLDS)
        self.assertEqual(boot.find_agent(self.key, fingerprint, [dead, empty, holding]), holding)

    def test_a_path_that_is_not_an_own_listening_socket_is_dead(self):
        fingerprint = boot.key_fingerprint(self.key)
        self.assertEqual(boot.agent_state(self.key, self.key, fingerprint), boot.DEAD, "a regular file")
        self.assertFalse(boot.own_socket(self.key))
        self.assertTrue(boot.own_socket(self.start_agent()))

    def test_the_fingerprint_is_read_without_the_pub_file(self):
        with_pub = boot.key_fingerprint(self.key)
        os.unlink(self.key + ".pub")
        self.assertEqual(boot.key_fingerprint(self.key), with_pub)

    def test_without_a_terminal_no_key_is_added(self):
        empty = self.start_agent()
        said = []
        env = {"SSH_AUTH_SOCK": empty, "XDG_RUNTIME_DIR": self.sock_dir}
        self.assertIsNone(boot.ensure_agent(said.append, interactive=False, key=self.key, env=env))
        self.assertTrue(any("no ssh-agent can sign" in line for line in said))
        fingerprint = boot.key_fingerprint(self.key)
        self.assertEqual(boot.agent_state(empty, self.key, fingerprint), boot.LIVE, "nothing was added")

    def test_the_key_is_added_once_to_the_live_agent(self):
        empty = self.start_agent()
        said = []
        env = {"SSH_AUTH_SOCK": empty, "XDG_RUNTIME_DIR": self.sock_dir}
        # The key has no passphrase, so ssh-add asks nothing here.
        self.assertEqual(boot.ensure_agent(said.append, interactive=True, key=self.key, env=env), empty)
        self.assertEqual(sum("type its passphrase once" in line for line in said), 1)
        said.clear()
        self.assertEqual(boot.ensure_agent(said.append, interactive=True, key=self.key, env=env), empty)
        self.assertEqual(said, [], "an agent that holds the key is used as it is")

    def test_with_no_live_agent_the_deck_starts_its_own(self):
        said = []
        env = {"SSH_AUTH_SOCK": os.path.join(self.sock_dir, "gone"), "XDG_RUNTIME_DIR": self.sock_dir}
        own = boot.own_agent_path(env)
        found = boot.ensure_agent(said.append, interactive=True, key=self.key, env=env)
        # ssh-agent -k needs the pid; the agent at `own` is the one listening there.
        self.addCleanup(subprocess.run, ["pkill", "-f", f"ssh-agent -a {own}"])
        self.assertEqual(found, own)
        self.assertEqual(boot.agent_state(own, self.key, boot.key_fingerprint(self.key)), boot.HOLDS)

    def test_a_link_to_an_agent_without_the_key_is_a_problem_until_it_holds_it(self):
        agent = self.start_agent()
        api = os.path.join(self.sock_dir, "api.sock")
        os.symlink(agent, api + ".agent")
        self.assertIn("does not hold", boot.link_problem(api, key=self.key))
        # herdr keeps a live inherited agent over a registered one: the key
        # goes into the agent the panes already use.
        said = []
        env = {"XDG_RUNTIME_DIR": self.sock_dir}
        self.assertEqual(boot.ensure_agent(said.append, interactive=True, key=self.key, env=env,
                                           first=boot.link_target(api)), agent)
        self.assertIsNone(boot.link_problem(api, key=self.key))

    def test_the_inherited_agent_gets_the_key_even_when_another_holds_it(self):
        inherited, other = self.start_agent("inherited"), self.start_agent("other")
        self.add_key(other)
        said = []
        env = {"SSH_AUTH_SOCK": other, "XDG_RUNTIME_DIR": self.sock_dir}
        # herdr's panes use the live inherited agent whatever is registered.
        self.assertEqual(boot.ensure_agent(said.append, interactive=True, key=self.key, env=env,
                                           first=inherited), inherited)
        self.assertEqual(boot.agent_state(inherited, self.key, boot.key_fingerprint(self.key)), boot.HOLDS)

    def test_without_a_terminal_the_panes_agent_is_named_as_the_one_lacking_the_key(self):
        inherited, other = self.start_agent("inherited"), self.start_agent("other")
        self.add_key(other)
        said = []
        env = {"SSH_AUTH_SOCK": other, "XDG_RUNTIME_DIR": self.sock_dir}
        self.assertIsNone(boot.ensure_agent(said.append, interactive=False, key=self.key, env=env,
                                            first=inherited))
        self.assertTrue(any(inherited in line and "panes use" in line for line in said), said)

    def test_a_dead_inherited_agent_is_passed_over(self):
        other = self.start_agent("other")
        self.add_key(other)
        env = {"SSH_AUTH_SOCK": other, "XDG_RUNTIME_DIR": self.sock_dir}
        self.assertEqual(boot.ensure_agent([].append, interactive=False, key=self.key, env=env,
                                           first=os.path.join(self.sock_dir, "gone")), other)

    def test_the_keyring_is_looked_for_in_the_runtime_directory(self):
        env = {"XDG_RUNTIME_DIR": self.sock_dir, "SSH_AUTH_SOCK": "/t/s"}
        self.assertEqual(boot.agent_candidates(env, first="/f"), [
            "/f", "/t/s", os.path.join(self.sock_dir, "keyring", ".ssh"), boot.own_agent_path(env)])

    def lister(self, *parts) -> str:
        return self.listing_agent(*parts)[0]

    def listing_agent(self, *parts) -> tuple[str, ListingOnlyAgent]:
        path = os.path.join(self.sock_dir, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        agent = ListingOnlyAgent(path, self.key + ".pub")
        self.addCleanup(agent.close)
        return path, agent

    def test_an_agent_that_lists_the_key_without_signing_is_not_holding_it(self):
        (lister, fake), holding = self.listing_agent("lister"), self.start_agent("holding")
        self.add_key(holding)
        fingerprint = boot.key_fingerprint(self.key)
        listed = subprocess.run(["ssh-add", "-l"], capture_output=True, text=True,
                                env=dict(os.environ, SSH_AUTH_SOCK=lister), stdin=subprocess.DEVNULL)
        self.assertIn(fingerprint, listed.stdout, "the control: the fake lists the key")
        self.assertEqual(boot.agent_state(lister, self.key, fingerprint), boot.LISTS)
        self.assertGreater(fake.asked, 0, "the listing agent was asked to sign")
        self.assertEqual(boot.find_agent(self.key, fingerprint, [lister, holding]), holding)

    def test_the_keyring_proxy_is_never_asked_to_sign(self):
        # Asked, it opens the desktop's unlock dialog (2026-10-30).
        proxy, fake = self.listing_agent("keyring", "ssh")
        fingerprint = boot.key_fingerprint(self.key)
        env = {"XDG_RUNTIME_DIR": self.sock_dir}
        self.assertTrue(boot.keyring_proxy(proxy, env))
        self.assertFalse(boot.keyring_proxy(os.path.join(self.sock_dir, "keyring", ".ssh"), env))
        self.assertEqual(boot.agent_state(proxy, self.key, fingerprint, env=env), boot.LISTS)
        self.assertEqual(boot.ensure_agent([].append, interactive=False, key=self.key,
                                           env=dict(env, SSH_AUTH_SOCK=proxy)), None)
        self.assertEqual(fake.asked, 0)

    def test_past_a_listing_proxy_the_keyring_agent_holding_the_key_is_chosen(self):
        # 2026-10-30: SSH_AUTH_SOCK named the keyring's proxy; its agent held the key.
        (proxy, fake), keyring = (self.listing_agent("keyring", "ssh"),
                                  self.start_agent(os.path.join("keyring", ".ssh")))
        self.add_key(keyring)
        said = []
        env = {"SSH_AUTH_SOCK": proxy, "XDG_RUNTIME_DIR": self.sock_dir}
        self.assertEqual(boot.ensure_agent(said.append, interactive=True, key=self.key, env=env),
                         keyring)
        self.assertEqual(said, [], "nothing to type")
        self.assertEqual(fake.asked, 0, "the proxy was never asked to sign")

    def test_with_only_a_listing_agent_the_key_is_added_once_to_the_decks_own(self):
        proxy = self.lister("proxy")
        said = []
        env = {"SSH_AUTH_SOCK": proxy, "XDG_RUNTIME_DIR": self.sock_dir}
        own = boot.own_agent_path(env)
        found = boot.ensure_agent(said.append, interactive=True, key=self.key, env=env)
        self.addCleanup(subprocess.run, ["pkill", "-f", f"ssh-agent -a {own}"])
        self.assertEqual(found, own)
        self.assertEqual(sum("type its passphrase once" in line for line in said), 1, said)
        self.assertEqual(boot.agent_state(own, self.key, boot.key_fingerprint(self.key)), boot.HOLDS)

    def test_with_only_a_listing_agent_and_no_terminal_nothing_is_started(self):
        proxy = self.lister("proxy")
        said = []
        env = {"SSH_AUTH_SOCK": proxy, "XDG_RUNTIME_DIR": self.sock_dir}
        self.assertIsNone(boot.ensure_agent(said.append, interactive=False, key=self.key, env=env))
        self.assertTrue(any("no ssh-agent can sign" in line for line in said), said)
        self.assertFalse(os.path.exists(boot.own_agent_path(env)), "no agent of the deck's own")

    def test_an_inherited_listing_agent_names_the_restart_and_gets_no_key(self):
        proxy, fake = self.listing_agent("proxy")
        holding = self.start_agent("holding")
        self.add_key(holding)
        said = []
        env = {"SSH_AUTH_SOCK": holding, "XDG_RUNTIME_DIR": self.sock_dir}
        asked = fake.asked
        self.assertIsNone(boot.ensure_agent(said.append, interactive=True, key=self.key, env=env,
                                            first=proxy))
        self.assertTrue(any("cannot sign" in line and "fleet-deck stop --all" in line
                            for line in said), said)
        self.assertFalse(any("type its passphrase" in line for line in said), said)
        self.assertEqual(fake.asked - asked, 1, "asked to sign once")

    def test_a_link_to_a_listing_agent_is_a_problem(self):
        proxy = self.lister("proxy")
        api = os.path.join(self.sock_dir, "api.sock")
        os.symlink(proxy, api + ".agent")
        problem = boot.link_problem(api, key=self.key)
        self.assertIn("cannot sign", problem)
        self.assertIn(boot.RESTART_SERVER, problem, "a registration cannot mend it")

    def test_an_inherited_keyring_proxy_is_not_taken_when_its_own_agent_holds_the_key(self):
        # That it then signs without a dialog was never seen; dialogs were.
        proxy, fake = self.listing_agent("keyring", "ssh")
        keyring = self.start_agent(os.path.join("keyring", ".ssh"))
        self.add_key(keyring)
        said = []
        env = {"XDG_RUNTIME_DIR": self.sock_dir}
        self.assertIsNone(boot.ensure_agent(said.append, interactive=True, key=self.key, env=env,
                                            first=proxy))
        self.assertTrue(any(boot.RESTART_SERVER in line for line in said), said)
        self.assertEqual(fake.asked, 0)

    def test_checking_an_agent_never_asks_the_keys_passphrase(self):
        locked = os.path.join(self.dir, "locked")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "a passphrase", "-f", locked],
                       check=True, stdin=subprocess.DEVNULL)
        asked = os.path.join(self.dir, "asked")
        askpass = os.path.join(self.dir, "askpass")
        with open(askpass, "w") as script:
            script.write(f"#!/bin/sh\necho asked >> '{asked}'\necho 'a passphrase'\n")
        os.chmod(askpass, 0o700)
        holding = self.start_agent("holding")
        prompting = dict(os.environ, SSH_ASKPASS=askpass, SSH_ASKPASS_REQUIRE="force",
                         DISPLAY=":0")
        subprocess.run(["ssh-add", "-q", locked], env=dict(prompting, SSH_AUTH_SOCK=holding),
                       check=True, capture_output=True, stdin=subprocess.DEVNULL)
        os.unlink(asked)  # the control: adding it asked once
        with mock.patch.dict(os.environ, prompting):
            state = boot.agent_state(holding, locked, boot.key_fingerprint(locked))
        self.assertEqual(state, boot.HOLDS)
        self.assertFalse(os.path.exists(asked), "the check asked for the passphrase")

    def test_no_key_starts_nothing(self):
        said = []
        self.assertIsNone(boot.ensure_agent(said.append, interactive=True,
                                            key=os.path.join(self.dir, "missing")))
        self.assertTrue(any("no deck key" in line for line in said))


class LinkTest(unittest.TestCase):
    def setUp(self):
        runtime = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self.dir = tempfile.mkdtemp(prefix="bl-", dir=runtime)
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.api = os.path.join(self.dir, "api.sock")

    def test_a_missing_link_is_named_with_its_remedy(self):
        problem = boot.link_problem(self.api)
        self.assertIn("is missing", problem)
        self.assertIn("fleet-deck stop --all", problem)

    def test_a_link_to_unavailable_is_a_problem(self):
        os.symlink(self.api + ".unavailable", self.api + ".agent")
        self.assertIn("leads to no live agent", boot.link_problem(self.api))

    def test_a_link_to_a_dead_socket_is_a_problem_and_a_live_one_is_not(self):
        target = os.path.join(self.dir, "agent")
        os.symlink(target, self.api + ".agent")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(target)
        self.addCleanup(listener.close)
        self.assertIsNotNone(boot.link_problem(self.api, key=None), "bound but not listening")
        listener.listen(1)
        self.assertIsNone(boot.link_problem(self.api, key=None))

    def test_no_server_socket_no_problem_said(self):
        self.assertIsNone(boot.link_problem(None))


class ProbeTest(unittest.TestCase):
    def serve(self, reply: bytes | None):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.addCleanup(listener.close)

        def once():
            conn, _ = listener.accept()
            with conn:
                if reply:
                    conn.sendall(reply)

        threading.Thread(target=once, daemon=True).start()
        return listener.getsockname()

    def test_a_greeting_sshd_passes(self):
        self.assertIsNone(boot.probe_sshd(*self.serve(b"SSH-2.0-OpenSSH_9.9\r\n")))

    def test_a_penalised_source_is_refused(self):
        # sshd's per-source penalty closes the connection before its banner.
        self.assertIn("without a greeting", boot.probe_sshd(*self.serve(None)))

    def test_nothing_listening_is_refused(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.close()
        self.assertIsNotNone(boot.probe_sshd("127.0.0.1", port, timeout=2))

    def test_the_pin_is_read_as_moveto_reads_it(self):
        def run(answer):
            return lambda *_a, **_k: subprocess.CompletedProcess([], 0, answer, "")
        self.assertEqual(boot.ssh_pin("a", run("ssh 127.0.0.1 22\n")), ("127.0.0.1", 22))
        self.assertIsNone(boot.ssh_pin("a", run("sudo\n")))
        with self.assertRaises(boot.PinUnreadable):
            boot.ssh_pin("a", run("something else\n"))
        with self.assertRaises(boot.PinUnreadable):
            boot.ssh_pin("a", lambda *_a, **_k: subprocess.CompletedProcess([], 1, "", "no registry"))


class AgentHoldTest(unittest.TestCase):
    """The registration, against a fake herdr API socket that answers as
    src/api/server.rs does."""

    def setUp(self):
        runtime = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self.dir = tempfile.mkdtemp(prefix="ah-", dir=runtime)
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, "api.sock")
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(self.path)
        self.listener.listen(4)
        self.addCleanup(self.listener.close)
        self.requests = []
        self.lines = []

    def serve(self, answers):
        """One connection per answer: read the request and answer it; a
        registration taken is held until `release` is set."""
        release = threading.Event()

        def run():
            for answer in answers:
                conn, _ = self.listener.accept()
                with conn:
                    self.requests.append(json.loads(boot.read_line(conn)))
                    conn.sendall((json.dumps(answer) + "\n").encode())
                    if "result" in answer:
                        release.wait(5)
                        release.clear()

        threading.Thread(target=run, daemon=True).start()
        return release

    def until(self, probe, seconds=5.0):
        deadline = time.monotonic() + seconds
        while not probe() and time.monotonic() < deadline:
            time.sleep(0.02)
        return probe()

    def start(self, hold):
        stopped = threading.Event()
        thread = threading.Thread(target=hold.run, kwargs={"sleep": lambda s: stopped.wait(0.01)},
                                  daemon=True)
        thread.start()
        return thread

    def test_registered_and_registered_again_when_the_server_lets_it_go(self):
        ok = {"id": "fleet-deck:ssh-agent", "result": {"type": "ok"}}
        release = self.serve([ok, ok])
        hold = boot.AgentHold("/run/agent.sock", lambda: self.path, self.lines.append)
        thread = self.start(hold)
        self.assertTrue(self.until(lambda: len(self.requests) == 1))
        self.assertEqual(self.requests[0], {"id": "fleet-deck:ssh-agent",
                                            "method": "server.ssh_agent.register",
                                            "params": {"socket_path": "/run/agent.sock"}})
        self.assertTrue(self.until(lambda: any("use the ssh-agent" in l for l in self.lines)))
        release.set()
        self.assertTrue(self.until(lambda: len(self.requests) == 2), "registered again")
        hold.close()
        thread.join(5)
        self.assertFalse(thread.is_alive(), "close ends the hold")

    def test_a_refusal_is_said_once_and_tried_again(self):
        refused = {"id": "fleet-deck:ssh-agent", "error": {
            "code": "invalid_ssh_agent", "message": "SSH agent must be an absolute, user-owned socket"}}
        self.serve([refused, refused, refused])
        hold = boot.AgentHold("/run/agent.sock", lambda: self.path, self.lines.append)
        thread = self.start(hold)
        self.assertTrue(self.until(lambda: len(self.requests) == 3))
        hold.close()
        thread.join(5)
        said = [l for l in self.lines if "refused the ssh-agent" in l]
        self.assertEqual(len(said), 1, self.lines)
        self.assertIn("user-owned socket", said[0])


if __name__ == "__main__":
    unittest.main()
