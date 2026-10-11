"""install: put this checkout's FleetDeck on the operator's login without
ending a session.

One command, run as the login that runs the fleet, from any terminal:

    <checkout>/fleet-deck/install [--dry-run] [--from-herdr] [--jobs N] [--bin-dir DIR]

It builds agent-fabric-fleetdeck once (release, `--jobs` bounded: the host
is shared), installs the binary by rename (a running server keeps the inode
it started from), links `fleet-deck` beside it, and then hands the running
server's panes to the new binary the way `update --handoff` does:

- a FleetDeck server (`agent-fabric-fleetdeck status server`) is asked for a
  live handoff to the installed binary;
- otherwise, and only with `--from-herdr`, a server of this fork from before
  the rename (`herdr`, 0.9.x) is asked by its own CLI for the same handoff.
  The new binary then serves the panes under FleetDeck's own directories,
  so the old `herdr` socket goes away and `agent-fabric-fleetdeck` attaches
  to them. Before it asks anything of that server, the command checks that
  `herdr` is this fork's build and refuses an upstream Herdr, which it
  never contacts (docs/fleetdeck/IDENTITY.md). Without the flag, a `herdr`
  on PATH is only named.

It never stops a server or a pane. A handoff the old server refuses or
cannot complete is rolled back by that server, which keeps running; the
command says so and exits non-zero. `--dry-run` builds and installs nothing
and asks no server to hand off: it prints what it would do, from the same
read-only status queries.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable

BIN = "agent-fabric-fleetdeck"
LEGACY_BIN = "herdr"
DECK_COMMANDS = ("fleet-deck",)

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)


@dataclass(frozen=True)
class Server:
    """What `<binary> status server --json` says about the server it reaches."""

    binary: str
    running: bool
    version: str | None
    live_handoff: bool
    socket: str | None


@dataclass(frozen=True)
class Step:
    """One thing the command does: a command line, or a note to the person."""

    argv: tuple[str, ...] | None
    say: str
    refuse: bool = False


def server_status(binary: str, run: Callable[..., subprocess.CompletedProcess]) -> Server | None:
    """The server `binary`'s own CLI reaches, or None when that CLI is absent
    or cannot say. Read-only: a status query starts nothing."""
    path = shutil.which(binary) if os.sep not in binary else binary
    if not path:
        return None
    try:
        result = run([path, "status", "server", "--json"], capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    capabilities = data.get("capabilities") or {}
    return Server(
        binary=path,
        running=bool(data.get("running")),
        version=data.get("version"),
        live_handoff=bool(capabilities.get("live_handoff")),
        socket=data.get("socket"),
    )


def is_forks_herdr(path: str, run: Callable[..., subprocess.CompletedProcess]) -> bool:
    """Whether the `herdr` at `path` is this fork's build from before the
    rename, asked without contacting any server: `--default-config` only
    prints the template. The fork's template carries `socket_access`, added
    by its first change (4af49a70) and absent from upstream Herdr's."""
    try:
        result = run([path, "--default-config"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "socket_access" in result.stdout


def checkout_problem(path: str, mode: int, owner: int, uid: int) -> str | None:
    """Why a checkout may not decide what this login installs, or None. The
    binary is built from it and `fleet-deck` stays linked into it, so a
    checkout another login owns or can write would choose what runs here."""
    if owner != uid:
        return f"{path} belongs to another login"
    if mode & 0o022:
        return f"{path} is writable by its group or by others"
    return None


def plan(
    *,
    root: str,
    bin_dir: str,
    jobs: int,
    profile: str = "release",
    new_version: str,
    fleetdeck: Server | None,
    legacy: Server | None,
    config_home: str,
    herdr_on_path: str | None = None,
    from_herdr: bool = False,
    herdr_is_fork: bool | None = None,
    config_exists: Callable[[str], bool] = os.path.exists,
) -> list[Step]:
    """Everything the command does, in order. Pure: the tests read it."""
    fleetdeck_running = bool(fleetdeck and fleetdeck.running)
    if from_herdr and herdr_on_path and not fleetdeck_running and herdr_is_fork is False:
        return [Step(None, f"`{herdr_on_path}` is not this fork's herdr (its default config has no "
                           "socket_access): it is another product, and FleetDeck never contacts it. "
                           "Nothing was built or installed", refuse=True)]
    installed = os.path.join(bin_dir, BIN)
    staged = os.path.join(bin_dir, f".{BIN}.new")
    steps = [
        Step(("cargo", "build", *(("--release",) if profile == "release" else ()), "--locked",
              "--jobs", str(jobs), "--bin", BIN),
             f"build {BIN} {new_version} ({profile}) from {root}"),
        Step(("install", "-m", "0755", os.path.join(root, "target", profile, BIN), staged),
             f"stage the binary beside {installed}"),
        Step(("mv", "-f", staged, installed),
             f"install {installed} by rename; a running server keeps the binary it started from"),
    ]
    # The import server reads FleetDeck's config, not herdr's: without this the
    # handed-off server would drop the operator's socket_access and keys. A
    # debug build reads the -dev directory (src/config/io.rs app_dir_name).
    app_dir = BIN if profile == "release" else f"{BIN}-dev"
    fleetdeck_config = os.path.join(config_home, app_dir, "config.toml")
    legacy_config = os.path.join(config_home, LEGACY_BIN, "config.toml")
    if not config_exists(fleetdeck_config) and config_exists(legacy_config):
        steps.append(Step(("mkdir", "-p", "-m", "0700", os.path.dirname(fleetdeck_config)),
                          f"create {os.path.dirname(fleetdeck_config)}"))
        steps.append(Step(("cp", "-n", "-p", legacy_config, fleetdeck_config),
                          f"copy your herdr config to {fleetdeck_config} (FleetDeck has none; "
                          "an existing one is never overwritten)"))
    for command in DECK_COMMANDS:
        steps.append(Step(("ln", "-sfn", os.path.join(root, "fleet-deck", command),
                           os.path.join(bin_dir, command)),
                          f"link {command} into {bin_dir}"))

    handoff = ("server", "live-handoff", "--import-exe", installed, "--expected-version", new_version)
    if fleetdeck_running:
        if fleetdeck.live_handoff:
            steps.append(Step((fleetdeck.binary, *handoff),
                              f"hand the running FleetDeck server's panes ({fleetdeck.version}) to {new_version}"))
        else:
            steps.append(Step(None, f"the running FleetDeck server ({fleetdeck.version}) offers no live "
                                    "handoff: it keeps running the binary it started from until you restart it"))
    elif legacy and legacy.running:
        if legacy.live_handoff:
            steps.append(Step((legacy.binary, *handoff),
                              f"hand the running herdr server's panes ({legacy.version}, {legacy.socket}) "
                              f"to {BIN} {new_version}"))
            steps.append(Step(None, f"attach with `{BIN}`; restart the deck with `fleet-deck restart`. "
                                    "Agents started under herdr keep herdr's socket and binary in their "
                                    "environment, so their hooks stop reporting state until each agent is "
                                    f"restarted under FleetDeck. Keep `{LEGACY_BIN}` installed until then"))
        else:
            steps.append(Step(None, f"the running herdr server ({legacy.version}) offers no live handoff: "
                                    "its panes stay on it; nothing was moved"))
    elif herdr_on_path and not from_herdr:
        steps.append(Step(None, f"a `{LEGACY_BIN}` command is on PATH ({herdr_on_path}); FleetDeck does not "
                                "contact it. If it is this fork's build from before the rename and its "
                                "server runs your agents, rerun with --from-herdr to hand its panes to FleetDeck"))
    else:
        steps.append(Step(None, f"no server is running: `{BIN}` or `fleet-deck` starts one"))
    return steps


def run_steps(steps: list[Step], *, dry_run: bool, cwd: str,
              run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
              say: Callable[[str], None] = lambda line: print(line, flush=True)) -> int:
    for step in steps:
        prefix = "would " if dry_run and step.argv else ""
        say(f"install: {prefix}{step.say}")
        if step.refuse:
            return 1
        if step.argv is None:
            continue
        say("  $ " + " ".join(step.argv))
        if dry_run:
            continue
        result = run(list(step.argv), cwd=cwd)
        if result.returncode != 0:
            if "live-handoff" in step.argv:
                say("install: the handoff did not complete: the server refused it, or rolled it back, "
                    "and keeps every pane; nothing was stopped. A server with "
                    "socket_access = \"outside_panes\" refuses a request from inside a pane: run this "
                    "from an ordinary terminal or a popup. The new binary is installed")
            else:
                say(f"install: stopped; `{step.argv[0]}` exited {result.returncode}")
            return 1
    return 0


def crate_version(root: str) -> str:
    with open(os.path.join(root, "Cargo.toml"), encoding="utf-8") as handle:
        in_package = False
        for line in handle:
            stripped = line.strip()
            if stripped.startswith("["):
                in_package = stripped == "[package]"
            elif in_package and stripped.startswith("version"):
                return stripped.split("=", 1)[1].strip().strip('"')
    raise SystemExit("install: no [package] version in Cargo.toml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleet-deck/install", description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the steps; build, install and hand off nothing")
    parser.add_argument("--jobs", type=int, default=4, help="cargo build jobs (default 4: the host is shared)")
    parser.add_argument("--bin-dir", default=os.path.join(os.path.expanduser("~"), ".local", "bin"))
    parser.add_argument("--profile", choices=("release", "debug"), default="release",
                        help="cargo profile to build and install (debug is for trying the command)")
    parser.add_argument("--from-herdr", action="store_true",
                        help="hand a running server of this fork's pre-rename `herdr` build to FleetDeck "
                             "(checked to be the fork's; an upstream Herdr is refused)")
    args = parser.parse_args(argv)

    for path in (ROOT, HERE):
        info = os.stat(path)
        problem = checkout_problem(path, info.st_mode, info.st_uid, os.getuid())
        if problem:
            print(f"install: refused: {problem}; run it from a checkout of your own", file=sys.stderr)
            return 1

    version = crate_version(ROOT)
    installed = os.path.join(args.bin_dir, BIN)
    fleetdeck = server_status(installed if os.path.exists(installed) else BIN, subprocess.run)
    herdr_on_path = shutil.which(LEGACY_BIN)
    herdr_is_fork = None
    legacy = None
    # herdr is asked nothing unless the operator named it, and its server
    # nothing unless it is this fork's own build.
    if args.from_herdr and herdr_on_path and not (fleetdeck and fleetdeck.running):
        herdr_is_fork = is_forks_herdr(herdr_on_path, subprocess.run)
        if herdr_is_fork:
            legacy = server_status(herdr_on_path, subprocess.run)
    steps = plan(
        root=ROOT,
        bin_dir=args.bin_dir,
        jobs=args.jobs,
        profile=args.profile,
        new_version=version,
        fleetdeck=fleetdeck,
        legacy=legacy,
        config_home=os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config"),
        herdr_on_path=herdr_on_path,
        from_herdr=args.from_herdr,
        herdr_is_fork=herdr_is_fork,
    )
    return run_steps(steps, dry_run=args.dry_run, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
