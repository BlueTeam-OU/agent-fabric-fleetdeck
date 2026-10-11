import subprocess
import unittest

import install_fleetdeck as install
from install_fleetdeck import Server, plan, run_steps

FLEETDECK = "/home/op/.local/bin/agent-fabric-fleetdeck"
HERDR = "/home/op/.local/bin/herdr"


def steps_for(fleetdeck=None, legacy=None, configs=(), profile="release", herdr_on_path=None,
              from_herdr=None, herdr_is_fork=None):
    if legacy is not None:
        herdr_on_path = herdr_on_path or HERDR
        from_herdr = True if from_herdr is None else from_herdr
        herdr_is_fork = True if herdr_is_fork is None else herdr_is_fork
    return plan(root="/src/fd", bin_dir="/home/op/.local/bin", jobs=4, profile=profile,
                new_version="0.10.0", fleetdeck=fleetdeck, legacy=legacy,
                config_home="/home/op/.config", config_exists=lambda path: path in configs,
                herdr_on_path=herdr_on_path, from_herdr=bool(from_herdr), herdr_is_fork=herdr_is_fork)


def commands(steps):
    return [step.argv for step in steps if step.argv]


class PlanTest(unittest.TestCase):
    def test_build_is_bounded_and_install_is_a_rename(self):
        argvs = commands(steps_for())
        self.assertEqual(argvs[0][:3], ("cargo", "build", "--release"))
        self.assertIn("--jobs", argvs[0])
        self.assertEqual(argvs[2], ("mv", "-f", "/home/op/.local/bin/.agent-fabric-fleetdeck.new", FLEETDECK))
        self.assertIn(("ln", "-sfn", "/src/fd/fleet-deck/fleet-deck", "/home/op/.local/bin/fleet-deck"), argvs)

    def test_a_running_herdr_server_is_handed_to_fleetdeck_by_its_own_cli(self):
        legacy = Server(HERDR, True, "0.9.3", True, "/home/op/.config/herdr/herdr.sock")
        argvs = commands(steps_for(legacy=legacy))
        self.assertEqual(argvs[-1], (HERDR, "server", "live-handoff", "--import-exe", FLEETDECK,
                                     "--expected-version", "0.10.0"))

    def test_a_running_fleetdeck_server_is_handed_off_before_any_herdr_one(self):
        fleetdeck = Server(FLEETDECK, True, "0.10.0", True, "s")
        legacy = Server(HERDR, True, "0.9.3", True, "h")
        argvs = commands(steps_for(fleetdeck=fleetdeck, legacy=legacy))
        self.assertEqual(argvs[-1][0], FLEETDECK)
        self.assertFalse(any(argv[0] == HERDR for argv in argvs))

    def test_nothing_stops_a_server(self):
        legacy = Server(HERDR, True, "0.9.3", False, "h")
        steps = steps_for(legacy=legacy)
        for argv in commands(steps):
            self.assertNotIn("stop", argv)
        self.assertFalse(any("live-handoff" in argv for argv in commands(steps)))
        self.assertIn("no live handoff", steps[-1].say)

    def test_no_server_means_no_handoff(self):
        self.assertFalse(any("live-handoff" in argv for argv in commands(steps_for())))

    def test_herdr_config_is_copied_only_when_fleetdeck_has_none(self):
        legacy_config = "/home/op/.config/herdr/config.toml"
        fleetdeck_config = "/home/op/.config/agent-fabric-fleetdeck/config.toml"
        copy = ("cp", "-n", "-p", legacy_config, fleetdeck_config)
        self.assertIn(copy, commands(steps_for(configs={legacy_config})))
        self.assertNotIn(copy, commands(steps_for(configs={legacy_config, fleetdeck_config})))
        self.assertNotIn(copy, commands(steps_for()))

    def test_a_debug_build_gets_the_config_in_the_directory_it_reads(self):
        legacy_config = "/home/op/.config/herdr/config.toml"
        dev_config = "/home/op/.config/agent-fabric-fleetdeck-dev/config.toml"
        argvs = commands(steps_for(configs={legacy_config}, profile="debug"))
        self.assertIn(("cp", "-n", "-p", legacy_config, dev_config), argvs)
        self.assertNotIn(("cp", "-n", "-p", legacy_config, dev_config),
                         commands(steps_for(configs={legacy_config, dev_config}, profile="debug")))

    def test_without_the_flag_a_running_herdr_server_is_never_handed_off(self):
        legacy = Server(HERDR, True, "0.9.3", True, "h")
        steps = steps_for(legacy=legacy, from_herdr=False)
        self.assertFalse(any(HERDR in argv for argv in commands(steps)))
        self.assertIn("--from-herdr", steps[-1].say)

    def test_from_herdr_refuses_when_it_cannot_act(self):
        no_herdr = steps_for(from_herdr=True)
        unanswered = steps_for(herdr_on_path=HERDR, from_herdr=True, herdr_is_fork=True)
        for steps in (no_herdr, unanswered):
            self.assertEqual(commands(steps), [])
            self.assertTrue(steps[0].refuse)
            self.assertNotIn("no server is running", steps[0].say)
            self.assertNotIn("None", steps[0].say)
        self.assertIn("no `herdr` on PATH", no_herdr[0].say)
        self.assertIn("gave no answer", unanswered[0].say)

    def test_without_the_flag_a_herdr_on_path_is_only_named(self):
        steps = steps_for(herdr_on_path=HERDR)
        self.assertFalse(any(HERDR in argv for argv in commands(steps)))
        self.assertIn("--from-herdr", steps[-1].say)

    def test_an_upstream_herdr_is_refused_before_anything_is_built(self):
        steps = steps_for(herdr_on_path=HERDR, from_herdr=True, herdr_is_fork=False)
        self.assertEqual(commands(steps), [])
        self.assertTrue(steps[0].refuse)
        said = []
        self.assertEqual(run_steps(steps, dry_run=False, cwd="/src/fd",
                                   run=lambda *a, **k: self.fail("ran a command"), say=said.append), 1)

    def test_the_handoff_note_says_migrated_agents_keep_herdrs_hooks(self):
        legacy = Server(HERDR, True, "0.9.3", True, "h")
        note = steps_for(legacy=legacy)[-1].say
        self.assertIn("until each agent is restarted", note)
        self.assertNotIn("no longer needed", note)


class ChecksTest(unittest.TestCase):
    def test_the_forks_herdr_is_told_apart_by_its_default_config(self):
        def answer(stdout, code=0):
            return lambda argv, **_: subprocess.CompletedProcess(argv, code, stdout, "")

        self.assertTrue(install.is_forks_herdr(HERDR, answer('# socket_access = "all"\n')))
        self.assertFalse(install.is_forks_herdr(HERDR, answer("[server]\n")))
        self.assertFalse(install.is_forks_herdr(HERDR, answer("socket_access", code=2)))

        def missing(argv, **_):
            raise FileNotFoundError(argv[0])

        self.assertFalse(install.is_forks_herdr(HERDR, missing))

    def test_a_checkout_another_login_owns_or_can_write_is_refused(self):
        self.assertIsNone(install.checkout_problem("/src/fd", 0o40755, 1000, 1000))
        self.assertIn("another login", install.checkout_problem("/src/fd", 0o40755, 1001, 1000))
        self.assertIn("writable", install.checkout_problem("/src/fd", 0o40775, 1000, 1000))
        self.assertIn("writable", install.checkout_problem("/src/fd", 0o40757, 1000, 1000))

    def test_a_status_answer_that_is_not_an_object_is_unknown(self):
        def answer(argv, **_):
            return subprocess.CompletedProcess(argv, 0, "[1, 2]", "")

        self.assertIsNone(install.server_status("/bin/sh", answer))


class RunTest(unittest.TestCase):
    def test_dry_run_executes_nothing(self):
        ran = []
        said = []
        legacy = Server(HERDR, True, "0.9.3", True, "h")
        code = run_steps(steps_for(legacy=legacy), dry_run=True, cwd="/src/fd",
                         run=lambda *a, **k: ran.append(a), say=said.append)
        self.assertEqual(code, 0)
        self.assertEqual(ran, [])
        self.assertTrue(any("would hand the running herdr server" in line for line in said))

    def test_a_refused_handoff_says_nothing_was_stopped(self):
        legacy = Server(HERDR, True, "0.9.3", True, "h")
        said = []

        def run(argv, **_):
            return subprocess.CompletedProcess(argv, 1 if "live-handoff" in argv else 0)

        code = run_steps(steps_for(legacy=legacy), dry_run=False, cwd="/src/fd", run=run, say=said.append)
        self.assertEqual(code, 1)
        self.assertIn("nothing was stopped", said[-1])

    def test_status_of_an_absent_cli_is_none(self):
        self.assertIsNone(install.server_status("/nonexistent/herdr-like", subprocess.run))


if __name__ == "__main__":
    unittest.main()
