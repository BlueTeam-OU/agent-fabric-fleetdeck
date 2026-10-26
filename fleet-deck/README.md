# Fleet Deck

The operator's console over the agent fleet, built into Agent Fabric FleetDeck.
It runs on Linux only, where agent-fabric's hosts run: it reads `/proc`,
asks a socket's peer with `SO_PEERCRED`, and drives accounts through `moveto`.
Each agent account gets one tab, labelled with its login, holding four
panes. The tab shows one of them at a time, full size: a yellow second row
under the tab names, `harness · shell · status · agent`, marks the one
shown, and a click or `ctrl+6` then F1-F4 shows another; the others keep
running unseen. The harness is shown after every deck restore. The row is
FleetDeck's (`ui.pane_tabs`, `keys.select_pane_tab`), and stays in a narrow
window, under its header, its cells shortened to the names, then the keys. A tab whose panes do not carry exactly those four
labels shows no second row, and the deck leaves all its panes in sight.

| pane | runs | for |
|---|---|---|
| **harness** (left, 65 %, focused) | `moveto <account> --wait` | one line, `<account> - Enter to activate`; Enter starts or resumes the account's session |
| **shell** (top right) | `moveto <account>`, while the tab is focused | a shell as the account; `paused: tab not focused` otherwise |
| **status** (right) | `moveto <account> --watch`, while the tab is focused | the account's status, read-only; `paused: tab not focused` otherwise |
| **agent** (bottom right) | `fabric-view agent --agent <account> --in-tab`, as the operator | the agent's screen, as the fleet board opens it on Enter; `prefix+a` shows it, and `prefix+a` again shows the harness (see Views) |

This directory exists only in gzapi-org's fork; upstream merges never
touch it. The contract is agent-fabric's `docs/fleet-deck/tab-states.md`
(agent-fabric#115). Its state machine is implemented in `deck_tabs.py`,
and the deck around it in `fabric_deck.py`.

## Start and stop

One command brings the whole deck back, from a fresh terminal on the
operator's human login:

```sh
fleet-deck
```

It starts FleetDeck's server if none answers, starts the deck controller if
none runs, and attaches this terminal to FleetDeck. Run it again, or from a
second terminal, and it only attaches: the server answers its socket, and
the controller holds a lock (`$XDG_STATE_HOME/fabric-deck/deck.lock`) that a
second one cannot take. Detach with **ctrl+6 q**; the deck goes on.

```sh
fleet-deck status    # the server, the controller, the panes' ssh-agent, the log, the prefix; exit 0 when both run, 3 otherwise
fleet-deck stop      # stops the controller (SIGTERM; its state stream goes with it)
fleet-deck restart   # stops the controller and starts a new one
fleet-deck start     # starts what is missing, without attaching
fleet-deck start --auto   # the same, then every agent, tier by tier, no Enter typed
fleet-deck stop --all     # every agent's session, the controller, the server, the control agents
fleet-deck snapshot board # a view printed as text, for an agent to read (see Views)
```

**The ssh-agent comes first.** Every pane enters its account with `ssh`,
using the operator's deck key `~/.ssh/fabric_deck` through the agent the
server gives its panes. That is the link `<server socket>.agent`, which
leads to the agent the server inherited. A server started without a live
agent gives its panes none, and each pane asks for the key's passphrase.
So `fleet-deck` starts no server and no controller until it has an agent
holding the key. Only a socket this login owns and listens on counts. It looks at this terminal's `SSH_AUTH_SOCK`, then the
desktop keyring's agent, then its own. If none holds the key, it runs
`ssh-add` once, here: you type the passphrase once. If no agent answers at
all, it starts one at `$XDG_RUNTIME_DIR/fabric-deck/agent.sock`.

A server already running with a dead link is not replaced: its panes would
go with it. Instead `fleet-deck hold-agent`, a small detached process,
registers the agent with the server and holds it. The deck controller does
not hold it, so stopping or restarting the controller leaves the panes'
agent alone. `status` says whether the link leads to a live agent that
holds the key. If it leads to a live agent without the key, the key is added
to that agent: herdr prefers the agent its server inherited over a
registered one, even when another agent holds the key. A plain `fleet-deck` still attaches to a server with a dead
link, and says that `fleet-deck restart` mends it. Panes that a server made
while it had no link at all keep asking for the passphrase. For those,
restart the server: `stop --all`, then `start --auto`.

**`start --auto`** boots the fleet once the coordinator is up:
1. Finds the agent, as above.
2. Probes the host's pinned sshd once (its banner only). If sshd refuses
   this host (its per-source penalty), it stops there with that line, and
   nothing is started.
3. Starts the server, the controller and the control agents. The control
   agents are started once `fabric-ctl` has `control-start`; until then
   this step says so and goes on.
4. Activates the panes in the order of their workspaces: C-Level,
   Infrastructure, Experts with Marketing, Legal and Accountants, every
   "… Developer" workspace, then any other.
   - The coordinator is never activated: it is up already. That is the
     account holding fabric-coordinator, wherever its tab is, and a
     Coordinator workspace on a deck seeded before the catalogue dropped it.
   - Within a tier, one agent every 4 s.
   - The next tier starts when the previous one is up, or after 60 s.
   - An agent counts as up when the fleet's state stream shows its
     session.
   - An agent whose moveto ends twice before its session comes up, or whose
     pane never shows the prompt, is named and skipped.

The boot presses the Enter that `moveto <account> --wait` asks for, and
nothing else. After the Enter, the prompt stays on screen while moveto
refreshes the account. So only a new moveto at the prompt (the deck armed
`--wait` again) counts as a failure, never the prompt alone. Over ssh the
prompt line is the account's own output, so the boot also needs the state
stream's fresh word that no session runs there. While that is unknown, it
does not press. It checks again just before each press, after the 4 s gap.
The boot presses only when the pane's foreground is that account's
`moveto --wait` and its last line is "<account> - Enter to activate". A
pane at a passphrase prompt, at a shell or running a harness is never
typed into. Without `--auto`, panes wait for your Enter as before.

While a boot runs, it holds `$XDG_STATE_HOME/fabric-deck/boot.lock`, and
no controller resumes a session on its own. This holds even across a
restart of herdr's server: an agent whose session ran before the stop
waits at `--wait` for its tier like the rest. A second `start --auto` refuses while one runs. Once the
boot ends, restores resume as before.

**`stop --all`** is the reverse:
1. Stops the controller, first, so that it does not arm the panes again.
2. Ends each pane's session, last tier first (SIGHUP to the pane's moveto,
   as closing the pane would), waiting up to 30 s per tier.
3. Stops the server and the ssh-agent holder.
4. Stops the control agents, once `fabric-ctl` has `control-stop`.

It then names any session still running: one outside the deck is left
running. The same is in the deck's menu as **Stop the whole fleet…**. Its
popup asks you to type `stop`, then runs `stop --all` detached, because
stopping the server closes the popup.

- **The controller has no terminal.** It runs in a session of its own, its
  input is `/dev/null`, and it writes to `$XDG_STATE_HOME/fabric-deck/deck.log`
  (one line per change, timestamped). Each time a controller starts, a log
  past 1 MiB is moved to `deck.log.1`; a controller that runs for weeks
  keeps writing to the same file. Closing a terminal or a FleetDeck tab never
  reaches it. Only `fleet-deck stop` or `restart` stops it.
- **`stop` never stops FleetDeck's server.** The server keeps every agent's pane
  running; `agent-fabric-fleetdeck server stop` would end them all. After a server restart the
  deck restores the tabs (see Restore).
- **The deck's options** (`--catalog`, `--exclude`, `--cwd`, `--no-fleet-tab`)
  are given to `fleet-deck` and take effect when it starts the controller;
  change them with `fleet-deck restart <options>`. The catalogue defaults to
  the agent-fabric checkout's (`AGENT_FABRIC_ROOT`, else
  `~/projects/agent-fabric`).
- **Outside FleetDeck's panes only.** `server.socket_access = "outside_panes"`
  refuses a pane's processes, so `fleet-deck` refuses to start anything from
  inside a pane (a FleetDeck popup is the operator's own and may).
- **Install**, and after each update of this checkout, run this on the
  operator's login, from an ordinary terminal (not a pane):
  `<this checkout>/fleet-deck/install` (`--dry-run` shows the steps; add
  `--from-herdr` the first time, while the fork still runs as `herdr`).
  - First it asks the build's Zig (`$ZIG`, else `zig` on PATH) for its
    version, and stops -- dry run included -- unless it is the release
    `vendor/libghostty-vt/build.zig.zon` names, saying where to get
    it. Nothing is built before that.
  - It builds `agent-fabric-fleetdeck` once (`--jobs 4` by default), installs it
    into `~/.local/bin` by rename, and links `fleet-deck` beside it.
  - If FleetDeck has no config yet, it copies `~/.config/herdr/config.toml`
    across. An existing config is never overwritten.
  - It then hands the running server's panes to the new binary by live
    handoff. A running FleetDeck server is handed off by its own CLI. With
    `--from-herdr`, a running `herdr` server of this fork from before the
    rename is handed off by `herdr`'s CLI, once the installer has checked
    that `herdr` is the fork's build (an upstream Herdr is refused), and its
    panes keep running under FleetDeck's directories. Afterwards, attach
    with `agent-fabric-fleetdeck` and run `fleet-deck restart`. Agents moved
    from `herdr` report state through their hooks again only once each is
    restarted under FleetDeck; keep `herdr` installed until then.
  - It never stops a server or a pane. A refused or failed handoff leaves the
    old server and every pane as they were.

`fabric-deck` is the controller itself; `fleet-deck` starts it. Run in a
terminal by hand, it still refuses to run beside another deck.

## Keys

Every pane runs a harness, so every key combination reaches it as typed:
ctrl+c, ctrl+v, ctrl+z, esc, PageUp and PageDown included, whether or not
something is selected or on the clipboard. FleetDeck keeps only these:

| key | FleetDeck's action |
|---|---|
| **ctrl+6** | the prefix: FleetDeck's commands are ctrl+6 then a key (`ctrl+6 q` detaches; the `prefix+f/a/p` keys in Views: `ctrl+6 a` turns an agent's tab between its harness and its agent screen); ctrl+6 twice sends ctrl+6 to the pane. A legacy terminal sends it as ctrl+^ (0x1e), which works too. |
| **ctrl+alt+c** | copies the selection |
| **ctrl+alt+p** | pastes the clipboard's text into the pane |
| **cmd+c / cmd+v** | copy (any system) and paste (macOS), where the terminal forwards cmd |
| **alt+PageUp / alt+PageDown** | scroll FleetDeck's scrollback, when the pane is on its main screen with no mouse reporting (otherwise they reach the pane) |
| the **mouse** | selection, menus and scrolling |

**Copying and pasting.**
- A mouse selection is copied as soon as the button is released, and stays
  highlighted until you click or type. ctrl+alt+c copies it again. The
  right-click menu has Copy and Paste.
- `ctrl+6 [` enters copy mode, to select and copy with the keyboard.
- ctrl+alt+p pastes, and so does the terminal's own paste (ctrl+shift+v in
  ptyxis, which Qubes' clipboard also uses). Either arrives as a paste in the
  pane. ctrl+v goes to the harness, which pastes itself (Claude Code reads an
  image from the clipboard).
- To scroll, use alt+PageUp/PageDown or the mouse wheel.
- `[ui] clipboard_shortcuts = false` gives ctrl+alt+p to the pane as well,
  and ctrl+alt+c unless `copy_on_select = false` (then it is the only key
  that copies a kept selection). A FleetDeck binding configured on either key
  wins over it.

**Why these keys.** Each was checked on 2026-10-10 against what the
harnesses bind, and against what the owner's desktop and terminal keep for
themselves (FleetDeck never receives those).
- **Claude Code:** its default keybindings in every context, chords by their
  first key, and its reserved keys (code.claude.com/docs/en/keybindings).
- **Codex CLI:** its built-in TUI keymap (openai/codex
  `codex-rs/tui/src/keymap.rs` at 806d9732). It binds ctrl+alt+v to paste an
  image, which is why FleetDeck's paste is ctrl+alt+p.
- **A plain shell:** bash's emacs keymap (`bind -p`), with its ESC-ctrl
  bindings counted as ctrl+alt (a legacy terminal sends ctrl+alt+x as ESC
  ctrl+x), and the tty's control characters (`stty -a`).
- **The desktop:**
  - dom0's Xfce: ctrl+alt+l and ctrl+alt+Escape;
  - ptyxis: alt+digits, alt+comma, ctrl(+shift)+PageUp/PageDown and
    ctrl+shift+c/v;
  - the Qubes clipboard: ctrl+shift+c/v.

Upstream's prefix, ctrl+b, is Claude Code's "background the task", and
Codex's and readline's backward-char. Upstream's plain PageUp/PageDown
scrolling, and this fork's earlier ctrl+c/ctrl+v copy and paste (60764f3f),
took keys every harness uses.

`src/client/shell/tests/harness_keys.rs` pins all of it:
- **The lists.** Each harness's keys and the desktop's are written there. The
  prefix, every default direct binding and FleetDeck's own keys are checked
  against them, and so are the `prefix+f/a/p` keys below.
- **Byte for byte.** Through FleetDeck's real input path, the keys a harness uses
  reach the pane exactly as typed, from a legacy terminal and from a kitty
  terminal. ctrl+c still does with a visible selection, and ctrl+v with text
  on the clipboard.
- **FleetDeck's own keys** never reach the pane.
- **ctrl+^.** A binding to it is refused beside the ctrl+6 prefix, since a
  legacy terminal sends both as one byte.

A `keys.prefix` in FleetDeck's config replaces ctrl+6; `fleet-deck` says when it
is one the check does not cover.

## Restore

When the deck starts, and whenever FleetDeck's server comes back after being
lost or replaced, every placed account (`moveto --list`, without the
deck's own login) gets its tab. An account placed while the deck runs
gets its tab within 10 s. One whose restore failed part-way is restored
again whole within 10 s, and is followed in nothing until then.
- **The tab.** A missing tab is created. On a host's first setup the role
  catalogue's group seeds the workspace; afterwards a new account goes to
  its group's workspace if one still exists, else to `New`. An account
  whose role is not bound yet (`moveto --list` shows `-`) gets no tab until
  it is, so its tab is made once, in its role's workspace, rather than in
  `New` and moved later (a FleetDeck from before tab move could not move it
  at all). The deck's log says so once. One that waited
  through the host's first setup is seeded as on first setup once bound.
  At a restore, an account's tab in `New` whose role's workspace exists is
  moved there with its panes running (`agent-fabric-fleetdeck tab move`); a
  tab a person put in any other workspace stays. A FleetDeck without tab
  move leaves it in `New`, said once in the deck's log.
- **A milestone-1 tab** (one unlabelled pane) keeps that pane as the
  harness and gains the shell, status and agent panes. A tab from before
  the agent pane gains one below its status pane.
- **A tab split by hand** with no `harness` pane is left alone, and the
  deck says so once.
- **The harness is the pane shown** after each restore of a tab of exactly
  the four panes: zoomed in its tab without switching to it (`pane zoom
  --in-tab`, FleetDeck's `pane.zoom_in_tab`), so a restore never takes the
  person through the tabs. Once a tab per run of restores: a restore retried
  for one account leaves its tab on the pane the person picked. If the zoom
  fails (a FleetDeck without that method, say), the tab shows every pane and
  the deck's log says why, once for each reason.
- **The shell and status panes** are started once their shell is at its
  prompt, since a pane just created may still be running the operator's
  rc file. One still busy after 120 s is said once, and started whenever
  it reaches its prompt. One already running this account's moveto is
  left as it is. Both hold their ssh only while their tab is the server's
  focused tab (the focused workspace's active tab, read at each look,
  every 2 s; with several clients attached, a tab another client shows is
  paused): when the tab loses focus the deck hangs up their moveto, as
  closing the pane would, and types `paused: tab not focused` at the
  shell it leaves, trying again at each look until herdr answers and the
  hang-up is taken; when the tab is focused again, the line at its
  prompt is cleared (`ctrl+u`, so a half-typed command is dropped, never
  run) and they are started again. So a shell pane's work ends with the
  focus. The harness pane is never touched by focus, and a pane running
  anything but this account's moveto is left as it is. Focus herdr cannot
  report, or no workspace focused, changes nothing.
- **The agent pane** is started the same way, with the agent's screen
  typed at the operator's prompt there; FleetDeck restores the pane as a
  shell, never its program. One already showing this account's screen is
  left as it is, and nothing is typed into one running anything else. As
  a screen turns focus reporting on, herdr answers with the focus its
  viewers really give the pane: in when some client whose terminal has
  focus shows it, out otherwise. So a screen started where a person is
  looking, or picked while it was starting, is live at once, and one
  nobody watches fetches nothing. The deck never tells a screen it starts
  a focus it can only infer: the pane list's focus is the server's default
  target, which may be no one's once the last client has detached. Under
  a herdr server older than that answer, such a screen says "press a key
  to go live" and fetches at that key; `prefix+a` waits for the screen
  instead, and so it is live at once there too. A screen seen
  running that has ended is started again at the next map read (10 s),
  once for each end.
- **A harness pane running this account's moveto** is classified and
  never touched.
- **Any other harness pane** waits until it is at the operator's prompt,
  and 5 s for the stream. That covers a bare pane, one just created, or
  one still busy (said once after 120 s; it never gets `--wait` in place
  of the decision). Then:
  - if a session runs on the account now, it gets a plain `moveto`
    shell, so an Enter there cannot start a second session;
  - if the account's session was running before the restart and none
    runs now, it gets `--resume`;
  - otherwise, or with no fresh record within 120 s, it gets `--wait`.

## What a person sees

The deck reports each harness pane into FleetDeck's agent panel as the agent
`claude` from the source `fabric`. FleetDeck's default agent row shows the
agent's name, so the deck's word goes in its place, and FleetDeck's own
`claude` comes back while a harness runs.

| state | FleetDeck state (icon, notifications) | the row reads |
|---|---|---|
| a harness runs in the pane | the session's: `working` or `idle` | `claude` |
| a harness runs, and its session waits on a person | `blocked` | why: `permission` or `question`; `needs you` where the session does not say |
| waiting for Enter | `idle` | `dormant` |
| the account's shell after a session ended here | `idle` | `shell` |
| a `--resume` the deck started, no harness yet | `working` | `restoring` |
| a `--resume` that produced no harness, or a moveto that ended at once twice | `blocked` | `failed` |
| moveto has no `--wait` yet, so the harness pane is left at the operator's shell | `unknown` | `unknown` |
| something other than this account's moveto holds the harness pane | `unknown` | `unknown` |
| a session runs on the account, not in this pane | `unknown` | `running elsewhere` |
| the account's record is older than two heartbeats, or says the account cannot read its session state (`state: unknown`) | `unknown` | `stale` |
| the same, while a harness runs and the account's newest record that lists sessions (ctl keeps them on a row it marks unknown) has one blocked: a person may still be wanted. A record that was already the account's newest when the deck last saw the pane without a harness belongs to an earlier session and does not count, unless a newer record arrives while the harness runs; for a harness already running when the deck started, any record counts | `blocked` | `stale` |

The same words are set as FleetDeck state labels, for a sidebar layout that
shows `state_text`. FleetDeck shows an `idle` the person has not looked at as
`done`, so the word is set for both. The deck's log prints one line per
change.

Each harness pane also carries the metadata token `account=<login>`, so
FleetDeck can tell the accounts apart although every pane reports as
`claude`: `[ui.sound.accounts."<login>"]` in FleetDeck's config gives an
account its own sound per state transition (see the Sound section of the
configuration docs). Sounds follow the FleetDeck state column above, the
deck's own states included: a `--resume` that fails (`working ->
blocked`) sounds as any agent that needs attention does.

## What the deck observes, and never does

- **moveto in the pane** comes from FleetDeck's `pane process-info`. The
  pane's foreground is moveto's `sudo … enter <dir> <title> [mode]`
  hand-off, or the operator's bare shell once moveto ended. A bare shell
  is its own foreground process group (`foreground_process_group_id ==
  shell_pid`).
- **A harness in the pane** is a `claude` process, or agent-fabric's
  `launch.py`, among the descendants of that `sudo`.
  - sudo runs the account in a pty of its own (`use_pty`), so the harness
    is never in the pane's foreground. The deck walks `/proc/<pid>/stat`
    parent links instead, and reads only `stat`, plus `cmdline` of those
    descendants.
  - This was measured live on develop-qzapp (GZCoord seq 22145); `/proc`
    is mounted without `hidepid`.
- **A pane entered over ssh** (`moveto --via ssh`, agent-fabric ADR-048)
  is the account's when its foreground is `ssh` connecting as the account
  with one of the forced command's four words as the whole remote command:
  `--wait`, `--watch`, `--resume`, or `shell` (plain). The argv is read as
  OpenSSH reads it: the user is the first one set, by `-l`, `-o User=` or
  `<login>@`; options after the destination are ssh's too, so a word that
  starts with `-` must follow `--` (`ssh <login>@<host> -- --wait`). It is classified, followed and never typed into, like a
  sudo pane.
  - sshd starts the account's session, so its harness is no descendant of
    the pane's `ssh`. The connection links them: the deck reads the local
    end (address and port) of each established TCP socket of the pane's
    own `ssh` (`/proc/<pid>/fd` and that process's `net/tcp`, `net/tcp6`;
    the process is the operator's), and enter-ssh records sshd's view of
    the same end, `SSH_CLIENT`, which the stream carries as a session's
    `ssh_client`. An IPv4-mapped IPv6 address compares as its IPv4 form.
  - A harness runs in the pane when a live session of the account carries
    one of those ends. Otherwise the pane is a sudo pane with no harness:
    `running elsewhere` while the account has a live session, idle when
    it has none.
  - A session whose ssh connected before enter-ssh recorded `ssh_client`
    carries no end. When no session of the account's record, live or
    over, carries one, exactly one is live, and only one tab bears the
    account's login, that session is taken as the pane's. A session that
    was never entered over ssh (a sudo or local start) then also shows as
    running there; an Enter there is still refused by `fabric-resume`.
    Any `ssh_client` in the record, a second live session or a second tab
    of the login leaves the pane to the match above.
  - When the deck reads no end (a ProxyJump or ProxyCommand ssh talks
    through a pipe, a ControlMaster client through a unix socket, and an
    ssh still connecting has no established socket), nothing links the
    pane to a session, and the account's live session is taken as the
    pane's: a session started elsewhere then shows as running there, and
    an Enter there is still refused by `fabric-resume`. A stale record
    changes nothing.
- **The account's sessions** come from `fabric-ctl all states --follow
  --json`, this host's records only. The stream is restarted after 1, 2,
  5, 10, 30, then 60 s.
- **FleetDeck's server instance** is the pid at the socket's other end
  (`SO_PEERCRED`) plus that process's start ticks.
  - The socket is the one the deck's FleetDeck commands reach, in FleetDeck's
    own order: `HERDR_SOCKET_PATH`, else the session `HERDR_SESSION`
    names, else the default session, each as `agent-fabric-fleetdeck session list --json`
    reports it. Inside a pane that a Herdr server started, the `HERDR_*`
    variables name that server and are ignored, as the binary ignores
    them (`docs/fleetdeck/IDENTITY.md`).
  - A different or unreadable instance is a loss of FleetDeck, and its next
    answer is a restore.
  - A failing `moveto --list` is not a loss: the last tab map stays.
- **What the deck does to panes:** it starts a fixed `moveto <account>
  [--wait|--resume|--watch]` only in the operator's own bare shell. While
  moveto runs, it never types into a pane, sends a key or closes one. A
  pane a person closes stays closed until the next restore.
- **A safeguard stop** is shown, never recovered by the deck. When an idle
  session's screen ends on Claude Code's own error for a turn the model's
  safeguards refused (both `API Error` and `safeguards flagged` in the
  last turn above the prompt box) for 60 s, the harness pane shows
  `blocked`, worded `safeguard stop`, so herdr's red and sound reach you.
  The deck logs the stop once and reports it once, as a GZCoord INFO to
  fabric-coordinator naming the agent and the time, never the refused
  text. It reads an idle pane's screen at most every 15 s, and nothing
  while the session works. A new stop, after the session moved on, is
  said and reported again. The stop hands the turn to a person by design:
  look at the screen, then answer it there.
- **A pane the deck stops following** gives back what the deck set: the
  agent row, the displayed name and the state labels. That covers a pane
  whose account left `moveto --list`, and one whose tab or label changed.
- **What the deck never does:** it never retries a failed `--resume`. One
  Enter in the re-armed `--wait` pane does that.
- **A moveto that keeps failing:** when a moveto the deck started ends
  within 15 s with no harness, twice in a row, the deck stops starting it.
  The row reads `failed`, the deck says so, and the pane's last lines say
  why. A person who starts moveto in that pane is followed again, and so
  is a restore.

Until agent-fabric's activation PR puts `--wait`, `--watch` and
`fabric-resume`'s second-session refusal on main, `moveto --help` does not
list them. The deck then arms no pane with them, says so once, and shows
those harness panes as FleetDeck's `unknown`.

## What the deck keeps

`$XDG_STATE_HOME/fabric-deck/before.json` (mode 0600) holds, per placed
account, whether its session was running. It is read only at a restore,
to decide `--resume`.
- **A rise** is written at once.
- **A fall** is written only once FleetDeck has visibly stayed up. That takes
  an answer from the same server instance as the last answer before the
  fall, at least 5 s after it. A fall seen around a loss of FleetDeck never
  settles, so a session that died with FleetDeck is resumed.
- **A fall still pending when the deck stops** is kept with its server
  instance. At the next start it settles only if that same server is
  still running.
- **An account that leaves `moveto --list`** is dropped at the next write.

## Views

`fabric-view` shows what the fleet does, as a fleet and per agent, in
FleetDeck plugin panes (`herdr-plugin.toml`, plugin `fabric.fleet`). Its data
is agent-fabric's `tools/fabric/fleet.py`, imported from the agent-fabric
checkout and never copied (agent-fabric ADR-046). The checkout is
`AGENT_FABRIC_ROOT`, else the one the installed `fabric-ctl` links into.

```sh
agent-fabric-fleetdeck plugin link <this checkout>/fleet-deck   # once, on the operator's login
```

and, in FleetDeck's `config.toml`, the keys:

```toml
[[keys.command]]
key = "prefix+f"
type = "plugin_action"
command = "fabric.fleet.board"
description = "fleet board"

[[keys.command]]
key = "prefix+a"
type = "plugin_action"
command = "fabric.fleet.agent"
description = "this agent"

[[keys.command]]
key = "prefix+p"
type = "plugin_action"
command = "fabric.fleet.prs"
description = "pull requests in flight"
```

The deck opens the board as a tab of its own, labelled `fleet`, in the
first workspace, unless one exists anywhere (`--no-fleet-tab` turns this
off). Like an account's pane, a fleet tab a person closes stays closed
until the next restore. FleetDeck's session restore brings a tab back by its
label but not a plugin pane's program: a `fleet` tab whose one pane is a
bare shell in the plugin's own directory (`fleet-deck/`, where FleetDeck
restores it) is the deck's, closed and replaced by the board. A pane whose
program has not started yet is looked at again at the next map read. A
`fleet` tab running anything else, or a shell elsewhere, is a person's,
left alone and said once.
Without the plugin linked, the deck says so once and restores the
account tabs as before.

| view | opens as | shows |
|---|---|---|
| **board** | the `fleet` tab | one row per placed agent, who needs you first: state, whether it needs you (and why, and for how long), what it waits on otherwise, current job, closed/working jobs, delivered jobs (handed over, waiting on someone else's merge; the first column a narrow board drops), RSS, CPU, tokens over 7 days, the 5-hour usage window, open PR; each host's memory and memory pressure below |
| **compare** | `c` in the fleet tab | one bar per agent for one metric: RSS, CPU, swap, tokens over 7 days, jobs done, working jobs, delivered jobs; largest first, scaled to the largest, labelled "operational, not a score" |
| **plan** | `p` in the fleet tab | each plan the coordinator keeps (agent-fabric ADR-047): its steps on a board by state (to do, queued, doing, delivered, done, and any other state), and a Gantt below |
| **PRs** | a popup (`fabric.fleet.prs`), or `P` in the fleet tab | in-flight pull requests by owner, each with its repository, title, work and fix commits, checks, review, armed, and the gate's verdict |
| **agent** | the account tab's agent pane, shown by `prefix+a` (`fabric.fleet.agent`); an overlay over a tab without that pane; or Enter on a board row | state, role, project, session, what it waits on; attention: whether it needs you and since when, its blocked and queued jobs, its context in use and whether output is landing, whether its inbox watch runs; resources, with a sparkline of the samples taken while open; working, delivered and closed jobs with their times; its PRs; tokens over 7 days; usage windows |

- **Keys.** ↑/↓ (or j/k), PgUp/PgDn, Home/End move. Enter on the board opens
  that agent, and Esc goes back to the board. In the fleet tab, `b`, `c`,
  `p` and `P` switch between board, compare, plan and PRs, and Esc leaves
  PRs for the screen it was opened from. In compare, ←/→ (or h/l, Tab)
  and 1-7 choose the metric; the chosen one is bracketed in the footer.
  `r` refetches the screen's sections once. `q` closes the pane, as does
  Esc on an overlay or the popup. On the board, `n` and `N` jump to the
  next and the previous agent that needs you, `s` switches between the
  needs-you order and the registry's, and `v` between the full board and a
  compact one (agent, needs you, current job); the footer says what each
  switches to.
- **The agent pane.** In an agent's tab, `prefix+a` (`ctrl+6 a`) shows
  the agent's screen, as `ctrl+6` F4 or a click on `agent` in the second
  row does, and `prefix+a` again shows the harness. The difference: a row
  pick only shows the pane, and an ended screen is started again by the
  deck at its next map read, where `prefix+a` starts it at once. Only the shown pane and
  the focus change: the harness's session runs on in its pane, and no second
  screen is ever opened. The screen fetches nothing until it is first
  focused, then refreshes only while focused, as every view: a deck start
  does not read the fleet once per tab. While its tab is not focused it
  rests: it draws only `paused: tab not focused`, and wakes on a focus
  report or a key rather than four times a second. A pane cannot call FleetDeck's
  socket (`outside_panes`), so the screen cannot leave itself: `q` and Esc
  do nothing there, and its footer names the chord. If its view has ended,
  `prefix+a` starts it again before showing it. In a tab with no agent
  pane (the deck has not restored it yet), `prefix+a` opens the overlay.
- **Needs you.** fleet.py's `attention` (agent-fabric `tools/fabric/fleet.py`),
  told in the view from the `states` and `jobs` records it already reads,
  with fleet.py's own reader: never fetched on its own. A session that waits
  on a person reads `permission`, `question`, or `needs you` where it does
  not say, with how long; an open job blocked on the owner (its own words,
  `blocked_on`, name the owner) reads `owner`, how long and those words.
  Only these two are counted in "n of N need you" and reached by `n`/`N`.
  A job waiting on anyone else is not in this column.
  The order is who needs you, then an idle agent with no inbox watch,
  then who cannot be told, then the rest; the longest waiting first.
- **Waiting on.** Each agent's longest-blocked job that waits on someone
  else: how long and its blocker, in the agent's own words (text only).
  A job whose checkable blockers all passed (fabric-jobs' `cleared`) reads
  `cleared: <blocker>`: the agent's to move on, not a wait. A job blocked
  on the owner is under needs you, unless it is cleared. What fleet.py could not tell is unknown (`?`, its
  why in the footer), never "nothing waits": the title counts it. In the
  agent view a context share or output activity not reported reads unknown,
  never 0 or quiet. Every colour (magenta for needs you, cyan for waiting)
  has its word beside it.
- **No inbox watch.** An agent whose session is idle, that nothing else
  has asked for the person, and whose account has run no `gzcoord-inbox`
  watch (as fleet.py's `inbox_watch` reports it) for 2 minutes or more reads
  `inbox off` and how long, in cyan, after who waits and before who cannot
  be told; the title counts it. It reads no message until a person wakes
  it: the deck types nothing into a session. The fact is fleet.py's proc
  `inbox_watch`; while fleet.py does not report it, every watch is unknown
  and nothing is flagged. The 2 minutes count from the first proc read
  this view fetched that found the watch missing, never from fleet.py's
  cache; a stale session state is not idle.
- **Compare.** A value that was not read has no bar and reads `…` or `?`,
  and is listed after the rest; the footer says why. "Jobs done" counts
  jobs closed as done, never dropped: fleet.py's `done_total`. Without
  it, the list of closed jobs is counted only when it is the whole list.
- **Plan.** A step's state is its job's (ADR-047). Each Gantt row is the
  step's id, owner, title and what it waits for (`⇠s1,s2`). A bar from the
  job's log (first active to last done, dropped or delivered; to now while
  running) is solid. A step with no time recorded is drawn hollow and
  marked `est`: it is placed after what it waits for, or at now, for its
  `est_days`, else one day. The `│` column is now. fabric-plan reads the
  plan files of the login it runs as, so on any login but the
  coordinator's the view says `no plans kept by <login>`.
- **PRs.** fleet.py reads fabric-pr gate in agent-fabric's checkout only,
  and the popup says so. A pushed branch without a PR is counted under its
  owner, not listed. A PR whose owner is no placed account is listed apart.
  A gate or GitHub that did not answer is said beside the owner. A
  fleet.py that does not list PRs of unplaced owners is said so.
- **The agent.** The overlay is that of the tab it was opened from: the
  deck labels an agent's tab with its login, and the view reads the label
  from `HERDR_PLUGIN_CONTEXT_JSON`. On any other tab it says so.
- **On demand.** At open, a view draws fleet.py's cache as it is, saying
  how old it is, and fetches. While the pane has focus (terminal focus
  reporting, DECSET 1004), it fetches each section again once that section's
  time to live has passed: 5 s for proc and states, up to 600 s for tokens
  (fleet.py's cost classes). When focus leaves, nothing new is fetched,
  and the status line leads with `PAUSED` and the oldest value's age,
  then the title, then how to go live: a board 13 hours old once read
  as the fleet now. A fetch already running finishes,
  since fleet.py bounds every source.
- **Focus starts unknown.** A view counts as focused from the first
  focus-in or key, and until then it stays at its open-time fetch, saying
  `press a key to go live`. FleetDeck answers the view's focus reporting
  with its real focus at once, so the wait lasts only while nobody is
  looking; a server older than that answer reports focus changes only,
  and there the words stay until a key. A view opened by its action (the
  keys above) is opened focused and starts live.
- **What a cell says.** `…` means not read yet. `?` means its section failed,
  and the board's footer says why, once per section. `-` means there is
  none. A value ending in `~` is stale: fleet.py's last good value, kept
  while a fresh read fails inside the section's stale window. The footer
  (board, compare), the owner's line (PRs) or the section (agent view)
  says whose, since when and why. The selected row is marked `>`, and every state is a word, never
  only a colour. `NO_COLOR` turns colour off.
- **Snapshot: how an agent reads the deck.** An agent never reads the
  owner's pane: it may be paused, it shows only what it scrolled to, and
  what is behind a key needs typing into it. Instead:

  ```sh
  fleet-deck snapshot board              # the fleet tab
  fleet-deck snapshot agent <login>      # Enter on that agent's row
  fleet-deck snapshot compare [--metric 1-7]
  fleet-deck snapshot plan
  fleet-deck snapshot prs
  ```

  Each fetches the view's sections once, as a pane does at open (each
  section's own TTL, fleet.py's cache within it), draws them with the
  pane's own renderer at `--width N` (default the terminal's, else 200),
  every row and the whole body, no row selected, and prints the text.
  The status line says `snapshot` where a pane says live or paused,
  beside the oldest value's age. A section still being read after 120 s
  is drawn `…` and named `reading` there. `fabric-view snapshot …` is
  the same command.
  - Exit 0 with the view on stdout. A section that failed alone is drawn
    as the pane draws it: `?`, and its why in the footer.
  - Exit 1, one line on stderr: the hosts registry or fleet.py cannot be
    read, or no section could.
  - Exit 2: usage, or a login that is no placed agent.

  It opens no pane and calls no FleetDeck socket, so it runs inside a
  pane too. What it reads is what the login running it may read (next).
- **Who can read what.** fleet.py's `jobs`, `usage`, `host`, `tokens` and
  `accounts` sections answer only a host operator. The views are meant for
  the operator's login; on any other they show those sections as `?`,
  with fabric-ctl's refusal.
- **What a view never does.** It calls no FleetDeck socket: `outside_panes`
  refuses a pane's process. The overlay is opened by the plugin's action,
  which FleetDeck runs outside the panes. A view sends no signed action and
  reads no other source than fleet.py.
- **What it writes.** Nothing of its own; it runs Python with `-B`.
  - fleet.py, which it calls, keeps its shared cache under
    `$XDG_RUNTIME_DIR/fabric-fleet/` (ADR-046 rule 2).
  - fleet.py's `prs` section runs pr-gate, which fetches origin in the
    agent-fabric checkout (fleet.py's documented side effect): at open,
    on `r`, and every 120 s while focused.
  - Quitting while a fetch is writing can leave one of fleet.py's
    temporary files in that cache directory.

## Tests

`just fleet-deck-test` runs the state machine (`test_deck_tabs`) and the
deck against a fake FleetDeck, a fake `/proc` and a real Unix socket
(`test_fabric_deck`), without a server. It also runs both views' layout on
fixture records (`test_view_render`, `test_report_render`), the views' input,
navigation, refresh rule and data location (`test_fabric_view`), and each
view's snapshot through a fake fleet.py (`test_snapshot`).

The deck was also run against a real, isolated FleetDeck server, with
stand-ins for `moveto` and `fabric-ctl`. The `moveto` stand-in has the
same `sudo … enter` argv shape and a pty of its own for the account's
shell. The run covered:
- restore, with `--resume` and `--wait`;
- Enter;
- a session ending;
- a deck restart that re-armed nothing;
- a FleetDeck server restart that resumed only the session that died with
  it.

The rendered FleetDeck client was inspected on a private X display. The real
`moveto`, `fabric-resume` and the fleet's stream have not been run with
it.
