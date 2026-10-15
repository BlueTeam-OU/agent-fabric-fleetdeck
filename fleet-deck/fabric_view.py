"""fabric-view: Fleet Deck's views of the fleet, in herdr plugin panes.

    fabric-view board                 the fleet tab: every placed agent, one
                                      row each; c compare, p plan, P PRs
    fabric-view agent [--agent L]     one agent; the login defaults to the
                                      herdr tab the pane was opened from
    fabric-view agent --agent L --in-tab
                                      the same, in the account tab's agent
                                      pane: it fetches at the first focus
    fabric-view toggle                for a plugin action: the account tab
                                      between its harness and agent screen
    fabric-view prs                   in-flight pull requests by owner
    fabric-view snapshot VIEW …       a view printed as text, read once
                                      (also `fleet-deck snapshot`)
    fabric-view open board|agent|prs  for a plugin action: open that pane

The data is agent-fabric's tools/fabric/fleet.py, imported from the
agent-fabric checkout, never copied (agent-fabric ADR-046). A view reads on
demand: at open it draws what fleet.py's cache holds, with its time, and
fetches; it refreshes each section by its cost class while the pane has
focus (terminal focus reporting, DECSET 1004) and stops when focus leaves;
`r` refetches every section once. A fetch already running when focus
leaves runs to its end (fleet.py's sources are bounded), and starts
nothing after it.

A view only reads. It calls no herdr socket: `server.socket_access =
"outside_panes"` refuses a pane's process, and the agent view takes its
login from HERDR_PLUGIN_CONTEXT_JSON instead. So the agent pane cannot
leave itself: the way back to the harness is the toggle's chord. `open` and
`toggle` are the only herdr calls, and they run as plugin actions, which
herdr places outside the panes.
"""

from __future__ import annotations

import datetime
import json
import os
import queue
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import report_render as rr
import view_render as vr
from deck_tabs import AGENT, HARNESS
# OPENED_FOCUSED: set by `open` for an overlay, which FleetDeck focuses
# before the view can hear it.
from fabric_deck import (BIN, OPENED_FOCUSED, SAFE_LOGIN, VIEW_START, Herdr, at_bare_shell, is_agent_view,
                         is_overlay_view, start_view, view_lock, view_mark, view_title,
                         wait_ready, DeckError)

FOCUS_ON = "\x1b[?1004h"
FOCUS_OFF = "\x1b[?1004l"
TICK_S = 0.25
TOKENS_DAYS = 7
PLUGIN_ID = "fabric.fleet"


# ── where agent-fabric is ───────────────────────────────────────────

def fabric_root(env: dict[str, str], which: Callable[[str], str | None] = shutil.which) -> str | None:
    """AGENT_FABRIC_ROOT, else the checkout the installed `fabric-ctl`
    belongs to (bin/ is a link into it): the same tree whose fleet.py the
    rest of the fleet runs."""
    root = env.get("AGENT_FABRIC_ROOT")
    if root:
        return root
    ctl = which("fabric-ctl")
    if not ctl:
        return None
    return os.path.dirname(os.path.dirname(os.path.realpath(ctl)))


def import_fleet(root: str):
    tools = os.path.join(root, "tools", "fabric")
    if not os.path.isfile(os.path.join(tools, "fleet.py")):
        raise ImportError(f"{tools} has no fleet.py: agent-fabric there predates fabric-fleet")
    sys.path.insert(0, tools)
    import fleet  # noqa: PLC0415 — found only once the root is known
    return fleet


def context_login(env: dict[str, str]) -> str | None:
    """The agent of the tab the overlay was opened from: the deck labels
    each agent's tab with its login."""
    try:
        ctx = json.loads(env.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
    except ValueError:
        return None
    label = ctx.get("tab_label") if isinstance(ctx, dict) else None
    return label.strip() if isinstance(label, str) and label.strip() else None


# ── input ───────────────────────────────────────────────────────────

FOCUS_IN = "focus-in"
FOCUS_OUT = "focus-out"
UP, DOWN, PAGE_UP, PAGE_DOWN, HOME, END = "up", "down", "page-up", "page-down", "home", "end"
LEFT, RIGHT = "left", "right"
ENTER, ESCAPE, BACK = "enter", "escape", "back"

SEQUENCES = {
    b"\x1b[I": FOCUS_IN, b"\x1b[O": FOCUS_OUT,
    b"\x1b[A": UP, b"\x1bOA": UP, b"\x1b[B": DOWN, b"\x1bOB": DOWN,
    b"\x1b[C": RIGHT, b"\x1bOC": RIGHT, b"\x1b[D": LEFT, b"\x1bOD": LEFT,
    b"\x1b[5~": PAGE_UP, b"\x1b[6~": PAGE_DOWN,
    b"\x1b[H": HOME, b"\x1bOH": HOME, b"\x1b[1~": HOME,
    b"\x1b[F": END, b"\x1bOF": END, b"\x1b[4~": END,
}
SINGLE = {b"\r": ENTER, b"\n": ENTER, b"\x7f": BACK, b"\x08": BACK, b"\x03": "q"}


def parse_input(buf: bytes, final: bool) -> tuple[list[str], bytes]:
    """Events from raw terminal bytes, and the bytes of an unfinished escape
    sequence to keep for the next read. `final` (no more bytes came) makes a
    lone ESC the Escape key. An unknown sequence is dropped whole, so its
    letters never act as keys."""
    events: list[str] = []
    i = 0
    while i < len(buf):
        b = buf[i:i + 1]
        if b != b"\x1b":
            events.append(SINGLE.get(b, b.decode("latin-1")))
            i += 1
            continue
        rest = buf[i:]
        if len(rest) == 1:
            if final:
                events.append(ESCAPE)
                i += 1
                continue
            return events, rest
        if rest[1:2] not in (b"[", b"O"):
            events.append(ESCAPE)   # ESC then a key: Escape, and the key next
            i += 1
            continue
        end = 2
        while end < len(rest) and not (0x40 <= rest[end] <= 0x7e):
            end += 1
        if end >= len(rest):
            if final:
                return events, b""
            return events, rest
        seq = rest[: end + 1]
        if seq in SEQUENCES:
            events.append(SEQUENCES[seq])
        i += end + 1
    return events, b""


# ── fetching ────────────────────────────────────────────────────────

@dataclass
class Refresher:
    """Which sections to fetch, and when: each section once at open,
    whatever the focus; then again once its TTL has passed since its last
    fetch ended, and only while focused. Pure: the clock and the starting
    are the caller's."""
    ttl: dict[str, float]
    finished: dict[str, float] = field(default_factory=dict)
    running: set[str] = field(default_factory=set)
    # Even the first fetch waits for focus: the agent pane of every account
    # tab starts with the deck, and one look per tab would be the fleet
    # fetched N times at once, for screens nobody sees.
    lazy: bool = False

    def due(self, now: float, focused: bool | None) -> list[str]:
        if self.lazy and focused is not True:
            return []
        return [s for s, ttl in self.ttl.items()
                if s not in self.running
                and (s not in self.finished or (focused is True and now - self.finished[s] >= ttl))]

    def refetch(self) -> list[str]:
        """`r`: every section not already being read."""
        return [s for s in self.ttl if s not in self.running]

    def started(self, section: str) -> None:
        self.running.add(section)

    def ended(self, section: str, now: float) -> None:
        self.running.discard(section)
        self.finished[section] = now


@dataclass
class Result:
    section: str
    records: dict[str, dict]      # login -> record
    why: str | None = None         # the whole fetch failed (fleet refused)
    asker: object = None           # the view whose fetch this was
    # Other records the same answer carried: {section: {key: record}}.
    extra: dict[str, dict[str, dict]] = field(default_factory=dict)


# The store's key for a record of the whole fleet rather than of one agent.
FLEET = ""
# Sections fleet.py answers once for the fleet, at the document's top level:
# a plan's steps belong to many agents, and to some not placed here.
FLEET_WIDE = frozenset({"plans"})
# The pull requests whose owner is no placed agent: one record, which fleet.py
# sends with any answer for `prs`.
UNPLACED = "prs_unplaced"


class Store:
    """The records a view shows, cached or fetched, per section and login."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, dict]] = {}
        self.fetched = False
        # login -> the read time (`at`) of the first proc record that found
        # no inbox watch, since the watch was last seen: how long it has
        # been missing, as far as this view has read.
        self.watch_missing: dict[str, str] = {}

    def put(self, section: str, records: dict[str, dict], fetched: bool = True) -> None:
        """Records to show. Only a fetched proc read times a missing watch:
        fleet.py's cache, put at open, may be days old, and the watch may
        have run any number of times since it was written."""
        self.records.setdefault(section, {}).update(records)
        if section == "proc" and fetched:
            for login, rec in records.items():
                running = inbox_watch(rec)
                if running is False and vr.parse_utc(rec.get("at")) is not None:
                    self.watch_missing.setdefault(login, rec["at"])
                elif running is True:
                    self.watch_missing.pop(login, None)

    def get(self, section: str, login: str) -> dict | None:
        return self.records.get(section, {}).get(login)


def cached_records(fleet, section: str, env: dict[str, str]) -> dict[str, dict]:
    """fleet.py's cache as it is, however old: drawn at open with its own
    `at`, so a person sees the last answer before the first fetch ends."""
    directory, _ = fleet.cache_dir(env)
    days = TOKENS_DAYS if section == "tokens" else None
    name = fleet.cache_name(type("Q", (), {"days": days})(), fleet.SECTIONS[section])
    return {login: e["record"] for login, e in fleet.cache_read(directory, name).items()}


class Fetcher:
    """Runs fleet.fetch for one section in a thread, results to a queue."""

    def __init__(self, fleet, agent: str | None, results: "queue.Queue[Result]", asker: object) -> None:
        self.fleet = fleet
        self.agent = agent
        self.results = results
        self.asker = asker

    def start(self, section: str, force: bool) -> None:
        threading.Thread(target=self._run, args=(section, force), daemon=True).start()

    def _run(self, section: str, force: bool) -> None:
        days = TOKENS_DAYS if section == "tokens" else None
        try:
            doc = self.fleet.fetch([section], self.agent, 0 if force else None, days=days)
            records, why, extra = answer_of(doc, section)
            self.results.put(Result(section, records, why, self.asker, extra))
        except Exception as e:  # noqa: BLE001 — a refusal is shown as that section's failure, never a crash
            self.results.put(Result(section, {}, f"{type(e).__name__}: {e}", self.asker))


def answer_of(doc: dict, section: str) -> tuple[dict[str, dict], str | None, dict[str, dict[str, dict]]]:
    """(records, why, extra) of fleet.py's document for one section."""
    if section in FLEET_WIDE:
        rec = doc.get(section)
        if not isinstance(rec, dict):
            return {}, f"fleet.py's answer has no {section}", {}
        return {FLEET: rec}, None, {}
    records = {a["login"]: a["sections"][section] for a in doc["agents"]}
    extra = {}
    if section == "prs":
        # An answer without it comes from a fleet.py that does not list
        # them: said, so their absence never reads as none in flight.
        extra[UNPLACED] = {FLEET: doc[UNPLACED] if isinstance(doc.get(UNPLACED), dict) else {
            "status": "failed", "src": "fleet", "at": doc.get("at"),
            "why": "agent-fabric's fleet.py here does not list them (no prs_unplaced)"}}
    return records, None, extra


# ── the views ───────────────────────────────────────────────────────

class View:
    """One screen: its sections, its refresher, its fetcher."""

    def __init__(self, fleet, sections: tuple[str, ...], agent: str | None, store: Store,
                 results: "queue.Queue[Result]", lazy: bool = False) -> None:
        self.sections = sections
        self.agent = agent
        self.store = store
        # A derived section is told here from the records its inputs' own
        # fetches bring (derive), never fetched: fleet.py gives it no TTL
        # and no cache, so a refresher would ask for it on every tick.
        self.refresher = Refresher({s: fleet.SECTIONS[s].ttl for s in sections
                                    if s in fleet.SECTIONS and not derived(fleet, s)}, lazy=lazy)
        self.fetcher = Fetcher(fleet, agent, results, self)
        # A section this agent-fabric's fleet.py does not serve yet is said,
        # never asked for: the view runs against whatever checkout is there.
        self.whys: dict[str, str] = {s: f"agent-fabric's fleet.py here serves no {s} section yet"
                                     for s in sections if s not in fleet.SECTIONS
                                     or (derived(fleet, s) and s not in DERIVE)}
        self.fleet = fleet
        # Read once and printed (`snapshot`): its status line says so, and
        # it marks no row selected.
        self.snapshot = False

    def tick(self, focused: bool | None) -> None:
        for s in self.refresher.due(time.monotonic(), focused):
            self.refresher.started(s)
            self.fetcher.start(s, force=False)

    def refetch(self) -> None:
        for s in self.refresher.refetch():
            self.refresher.started(s)
            self.fetcher.start(s, force=True)

    def owns(self, result: Result) -> bool:
        return result.asker is self

    def take(self, result: Result) -> None:
        self.refresher.ended(result.section, time.monotonic())
        if result.why:
            self.whys[result.section] = result.why
        else:
            self.whys.pop(result.section, None)


def inbox_watch(rec: dict | None) -> bool | None:
    """fleet.py's proc `inbox_watch`: True, False, or None where it is not
    reported (a fleet.py from before it, a stale or failed read, null)."""
    if not isinstance(rec, dict) or rec.get("status") != "ok":
        return None
    value = (vr.ok_data(rec) or {}).get("inbox_watch")
    return value if isinstance(value, bool) else None


def watch_of(proc: dict | None, missing_since: str | None) -> dict | None:
    """The `watch` record the views draw: the proc read's answer and, when
    missing, since when. None while proc is unread."""
    if proc is None:
        return None
    running = inbox_watch(proc)
    return {"status": "ok", "src": "derived:proc", "at": proc.get("at"),
            "data": {"running": running, "missing_since": missing_since if running is False else None}}


def derived(fleet, section: str) -> bool:
    spec = fleet.SECTIONS.get(section)
    return bool(getattr(spec, "derives", ()))


def attention_of(fleet, recs: dict[str, dict | None], now: float) -> dict | None:
    """fleet.py's own attention record, told from the states and jobs
    records this view holds (fleet.attention_record: imported, never
    copied, so the board and fabric-fleet --json cannot disagree). None
    while either is unread: not known yet, never "nothing waits"."""
    states, jobs = recs.get("states"), recs.get("jobs")
    if states is None or jobs is None:
        return None
    try:
        return fleet.attention_record(states, jobs, now)
    except Exception as e:  # noqa: BLE001 — a record fleet.py cannot read is that agent's failure, never a crash
        return {"status": "failed", "src": "fleet", "at": None, "why": f"{type(e).__name__}: {e}"}


# The derived sections this view can tell, and the fleet.py reader for each.
DERIVE: dict[str, Callable] = {"attention": attention_of}


def agents_of(placements, store: Store, sections: tuple[str, ...], whys: dict[str, str],
              fleet=None) -> list[vr.Agent]:
    out = []
    now = time.time()
    for login, a in placements.items():
        recs = {}
        for s in sections:
            rec = store.get(s, login)
            if s in whys:
                # The last fetch of the whole section failed: an older
                # record drawn as current would hide it.
                rec = {"status": "failed", "src": "fleet", "at": None, "why": whys[s]}
            recs[s] = rec
        for s, reader in DERIVE.items():
            if s in sections and s not in whys and fleet is not None:
                recs[s] = reader(fleet, recs, now)
        if "proc" in sections:
            recs["watch"] = watch_of(recs.get("proc"), store.watch_missing.get(login))
        out.append(vr.Agent(login, a.host, a.kind, recs))
    return out


def status(view: View, agents: list[vr.Agent], focused: bool, store: Store) -> vr.Status:
    records = [r for a in agents for s, r in a.sections.items() if s in view.sections]
    return vr.Status(focused=focused, fetching=tuple(s for s in view.sections if s in view.refresher.running),
                     now=datetime.datetime.now(datetime.timezone.utc), oldest=vr.oldest_at(records),
                     from_cache=not store.fetched, snapshot=view.snapshot)


# ── the terminal ────────────────────────────────────────────────────

class Painter:
    def __init__(self, curses, screen) -> None:
        self.curses = curses
        self.screen = screen
        c = curses
        self.attrs = {vr.NORMAL: c.A_NORMAL, vr.DIM: c.A_DIM, vr.BOLD: c.A_BOLD,
                      vr.SELECTED: c.A_REVERSE, vr.FAILED: c.A_BOLD, vr.WARN: c.A_BOLD,
                      vr.NEEDS: c.A_BOLD, vr.WAITING: c.A_NORMAL}
        if c.has_colors() and not os.environ.get("NO_COLOR"):
            c.start_color()
            c.use_default_colors()
            c.init_pair(1, c.COLOR_RED, -1)
            c.init_pair(2, c.COLOR_YELLOW, -1)
            c.init_pair(3, c.COLOR_MAGENTA, -1)
            c.init_pair(4, c.COLOR_CYAN, -1)
            self.attrs[vr.FAILED] = c.color_pair(1)
            self.attrs[vr.WARN] = c.color_pair(2)
            # Not red or yellow, which mean failed and stale here: wanted is
            # neither. Bold too, so it stands out where hues are hard to tell.
            self.attrs[vr.NEEDS] = c.color_pair(3) | c.A_BOLD
            self.attrs[vr.WAITING] = c.color_pair(4)

    def paint(self, lines: list[vr.Line]) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        for y, line in enumerate(lines[:height]):
            x = 0
            for text, style in line:
                if x >= width:
                    break
                # The bottom-right cell cannot be written without scrolling.
                room = width - x - (1 if y == height - 1 else 0)
                part = vr.take(vr.clean(text), room)
                try:
                    self.screen.addstr(y, x, part, self.attrs.get(style, 0))
                except (self.curses.error, UnicodeEncodeError):
                    pass   # a cell the terminal cannot take stays blank, never a crash
                x += vr.cells(part)
        self.screen.refresh()


# The fleet tab's screens, and the PRs popup's one.
BOARD, COMPARE, PLAN, PRS = "board", "compare", "plan", "prs"
SCREEN_SECTIONS = {BOARD: vr.BOARD_SECTIONS, COMPARE: rr.COMPARE_SECTIONS, PLAN: ("plans",), PRS: ("prs",)}
SCREEN_KEYS = {"b": BOARD, "c": COMPARE, "p": PLAN, "P": PRS}
QUIT, OPEN_AGENT, REFETCH = "quit", "open-agent", "refetch"


@dataclass
class Nav:
    """Where a person is in a fleet pane, moved by keys. Pure: the loop
    draws what it says and does what `key` returns. `back` is the screen Esc
    returns to from the PRs screen; None where PRs is the pane itself (the
    popup), so Esc closes it as any overlay."""
    screen: str
    metric: int = 0
    selected: int = 0
    scroll: int = 0
    back: str | None = None
    # The board: the rows as last drawn, and the agent selected among them.
    # The selection follows the agent, not the row, when the order changes.
    rows: list[vr.Agent] = field(default_factory=list)
    login: str | None = None
    needs_first: bool = True
    compact: bool = False
    notice: str | None = None

    def place(self, rows: list[vr.Agent]) -> None:
        """The board's rows in the order drawn: the selection stays on its
        agent wherever that agent now is."""
        self.rows = rows
        logins = [a.login for a in rows]
        if self.login in logins:
            self.selected = logins.index(self.login)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        self.login = logins[self.selected] if rows else None

    def go(self, screen: str) -> None:
        if screen == self.screen:
            return
        self.back = self.screen if screen == PRS else None
        self.screen, self.scroll = screen, 0

    def key(self, ev: str, rows: int, page: int) -> str | None:
        self.notice = None
        if ev in ("q", "Q"):
            return QUIT
        if ev == "r":
            return REFETCH
        if self.screen == PRS and ev in (ESCAPE, BACK):
            if self.back is None:
                return QUIT
            self.screen, self.scroll, self.back = self.back, 0, None
            return None
        # The popup is PRs alone; in the fleet tab every screen is a key away.
        if ev in SCREEN_KEYS and (self.screen != PRS or self.back is not None):
            self.go(SCREEN_KEYS[ev])
            return None
        if self.screen == BOARD:
            if ev == ENTER and rows:
                return OPEN_AGENT
            if ev == "s":
                self.needs_first = not self.needs_first
                return None
            if ev == "v":
                self.compact = not self.compact
                return None
            if ev in ("n", "N"):
                found = vr.next_needing(self.rows, self.selected, 1 if ev == "n" else -1) if self.rows else None
                if found is None:
                    self.notice = vr.none_needing(self.rows)
                else:
                    self.selected = found
            else:
                self.selected = max(0, min(move(self.selected, ev, page, rows - 1), max(0, rows - 1)))
            if self.rows:
                self.login = self.rows[min(self.selected, len(self.rows) - 1)].login
            return None
        if self.screen == COMPARE:
            n = len(rr.METRICS)
            if ev in (RIGHT, "l", "\t"):
                self.metric = (self.metric + 1) % n
            elif ev in (LEFT, "h"):
                self.metric = (self.metric - 1) % n
            elif len(ev) == 1 and ev.isdigit() and 1 <= int(ev) <= n:
                self.metric = int(ev) - 1
            else:
                self.scroll = move(self.scroll, ev, page, 1 << 16)
            return None
        self.scroll = move(self.scroll, ev, page, 1 << 16)
        return None


def run(curses, screen, fleet, mode: str, login: str | None, in_tab: bool = False) -> int:
    curses.curs_set(0)
    curses.raw()
    curses.noecho()
    # In the tab, the title after focus reporting: its sign, read from
    # outside, that a focus change now reaches it (fabric_deck.start_view).
    title = in_tab_title(login, os.environ) if in_tab else None
    sys.stdout.write(FOCUS_ON + (f"\x1b]2;{title}\x07" if title else ""))
    sys.stdout.flush()
    painter = Painter(curses, screen)
    ascii_only = "utf" not in (sys.stdout.encoding or "").lower()
    env = dict(os.environ)
    try:
        placements = fleet.load_placements(fleet.roots.engine_root())
    except Exception as e:  # noqa: BLE001
        return show_message(curses, screen, painter, "Fleet", f"The hosts registry could not be read:\n{e}")
    if mode == "agent" and login not in placements:
        where = f"the tab {login!r}" if login else "this tab"
        return show_message(curses, screen, painter, "Agent",
                            f"{where} is not a placed agent's.\n"
                            "Open this view from an agent's tab, whose label is its login.")

    store = Store()
    for s in set(vr.BOARD_SECTIONS) | set(vr.AGENT_SECTIONS) | set(rr.COMPARE_SECTIONS):
        if s in fleet.SECTIONS and derived(fleet, s):
            continue    # no cache of its own: told from its inputs' records
        try:
            store.put(s, cached_records(fleet, s, env), fetched=False)
        except Exception:  # noqa: BLE001 — a cache that cannot be read is an empty one
            pass
    results: "queue.Queue[Result]" = queue.Queue()
    # One View per screen, made when first shown: a screen never looked at
    # never fetches.
    views: dict[str, View] = {}

    def view_of(name: str) -> View:
        if name not in views:
            views[name] = View(fleet, SCREEN_SECTIONS[name], None, store, results)
        return views[name]

    nav = Nav(PRS if mode == "prs" else BOARD)
    agent_view = View(fleet, vr.AGENT_SECTIONS, login, store, results, lazy=in_tab) if mode == "agent" else None
    samples = vr.Samples()
    scroll = 0
    # Unknown until herdr reports a change or a key arrives, unless `open`
    # says the pane was opened focused. herdr reports focus changes only,
    # and a pane opened in the background never had focus to lose:
    # assuming focus at open would fetch in the background. A marked view
    # (in an agent pane) is told its focus once it can hear it
    # (fabric_deck.start_view), and trusts no hint.
    focused = initial_focus(env)
    # A refetch asked for with `r`, run once the input it came with is read.
    refetch_asked: View | None = None
    pending = b""
    size = None
    while True:
        current = agent_view or view_of(nav.screen)
        while True:
            try:
                r = results.get_nowait()
            except queue.Empty:
                break
            store.put(r.section, r.records)
            for section, records in r.extra.items():
                store.put(section, records)
            store.fetched = store.fetched or not r.why
            for v in [*views.values(), agent_view]:
                if v is not None and v.owns(r):
                    v.take(r)
            if agent_view and r.section == "proc":
                samples.add(store.get("proc", agent_view.agent))
        now_size = os.get_terminal_size(sys.stdout.fileno())
        if now_size != size:
            size = now_size
            curses.resizeterm(size.lines, size.columns)
        height, width = screen.getmaxyx()
        if agent_view is not None:
            a = agents_of({agent_view.agent: placements[agent_view.agent]}, store, agent_view.sections,
                          agent_view.whys, fleet)[0]
            keys = vr.TAB_KEYS if in_tab else vr.OVERLAY_KEYS if mode == "agent" else vr.AGENT_KEYS
            lines, scroll = vr.agent_lines(a, samples, status(agent_view, [a], focused, store), scroll,
                                           width, height, keys, ascii_only)
        else:
            lines = screen_lines(nav, current, placements, store, focused, width, height, ascii_only)
        painter.paint(lines)

        ready, _, _ = select.select([sys.stdin], [], [], TICK_S)
        if ready:
            chunk = os.read(sys.stdin.fileno(), 4096)
            if not chunk:
                return 0
            events, pending = parse_input(pending + chunk, final=False)
        else:
            events, pending = parse_input(pending, final=True)
        page = max(1, height - 4)
        for ev in events:
            if ev in (FOCUS_IN, FOCUS_OUT):
                focused = ev == FOCUS_IN
                continue
            focused = True    # a key reached this pane, so it has focus
            if agent_view is not None:
                if ev == "r":
                    refetch_asked = agent_view
                elif in_tab and ev in ("q", "Q", ESCAPE):
                    # Nothing to close: ended, the pane would be a bare shell
                    # where the agent's screen was. The chord leaves it.
                    continue
                elif ev in ("q", "Q") or (ev == ESCAPE and mode == "agent"):
                    return 0
                elif ev in (ESCAPE, BACK, "h") and mode != "agent":
                    agent_view, samples, scroll = None, vr.Samples(), 0
                else:
                    scroll = move(scroll, ev, page, 1 << 16)
                continue
            action = nav.key(ev, len(placements), page)
            if action == QUIT:
                return 0
            if action == REFETCH:
                refetch_asked = view_of(nav.screen)
            elif action == OPEN_AGENT:
                target = nav.login if nav.login in placements else list(placements)[max(0, min(nav.selected, len(placements) - 1))]
                agent_view = View(fleet, vr.AGENT_SECTIONS, target, store, results)
                samples, scroll = vr.Samples(), 0
                samples.add(store.get("proc", target))
        # Fetches are decided after the input is read, never before: a focus
        # report queued while the view started (a second press moving the
        # focus away) is applied first, so nothing is fetched for a pane
        # already hidden. The first fetch waits one tick for it.
        # `r` too: run once the focus that came with it is known, and only
        # while focused (pressed and left at once, it waits for the focus to
        # come back). Before the tick: a section the tick would start unforced
        # is then already running, forced, as `r` asks.
        if refetch_asked is not None and focused is True:
            refetch_asked.refetch()
            refetch_asked = None
        (agent_view or view_of(nav.screen)).tick(focused)


def screen_lines(nav: Nav, view: View, placements, store: Store, focused: bool | None,
                 width: int, height: int | None, ascii_only: bool) -> list[vr.Line]:
    """The fleet pane's current screen. Each screen reads its own view's
    sections, so its status line says how old what it shows is. A height
    of None draws the whole screen, unscrolled: a snapshot."""
    agents = agents_of(placements, store, view.sections, view.whys, view.fleet)
    if nav.screen == BOARD:
        nav.place(vr.board_order(agents, nav.needs_first, datetime.datetime.now(datetime.timezone.utc)))
        return vr.board_lines(nav.rows, host_records(agents), status(view, agents, focused, store),
                              None if view.snapshot else nav.selected, width, height, nav.needs_first,
                              nav.compact, nav.notice)
    if nav.screen == COMPARE:
        lines, nav.scroll = rr.compare_lines(agents, nav.metric, status(view, agents, focused, store),
                                             nav.scroll, width, height, ascii_only)
        return lines
    if nav.screen == PLAN:
        rec = fleet_record(store, "plans", view.whys)
        st = fleet_status(view, [rec], focused, store)
        lines, nav.scroll = rr.plan_lines(rec, st, nav.scroll, width, height, ascii_only)
        return lines
    keys = rr.PRS_KEYS if nav.back is None else rr.PRS_IN_TAB_KEYS
    unplaced = store.get(UNPLACED, FLEET)
    lines, nav.scroll = rr.prs_lines(agents, unplaced, status(view, agents, focused, store),
                                     nav.scroll, width, height, keys)
    return lines


def fleet_record(store: Store, section: str, whys: dict[str, str]) -> dict | None:
    if section in whys:
        return {"status": "failed", "src": "fleet", "at": None, "why": whys[section]}
    return store.get(section, FLEET)


def fleet_status(view: View, records: list, focused: bool | None, store: Store) -> vr.Status:
    return vr.Status(focused=focused, fetching=tuple(s for s in view.sections if s in view.refresher.running),
                     now=datetime.datetime.now(datetime.timezone.utc), oldest=vr.oldest_at(records),
                     from_cache=not store.fetched, snapshot=view.snapshot)


def host_records(agents: list[vr.Agent]) -> dict[str, dict | None]:
    """One `host` record per machine: every agent on it carries the same
    machine, so the freshest answer stands for it."""
    out: dict[str, dict | None] = {}
    for a in agents:
        rec = a.sections.get("host")
        best = out.get(a.host)
        if a.host not in out or (rec is not None and (best is None or vr.failed(best)
                                                      or (vr.ok_data(rec) is not None and str(rec.get("at")) > str(best.get("at"))))):
            out[a.host] = rec
    return out


def move(pos: int, ev: str, page: int, last: int) -> int:
    step = {UP: -1, "k": -1, DOWN: 1, "j": 1, PAGE_UP: -page, PAGE_DOWN: page}.get(ev)
    if step is not None:
        return max(0, pos + step)
    if ev in (HOME, "g"):
        return 0
    if ev in (END, "G"):
        return last
    return pos


def show_message(curses, screen, painter: Painter, title: str, text: str) -> int:
    pending = b""
    while True:
        height, width = screen.getmaxyx()
        painter.paint(vr.message_lines(title, text, "q close", width, height))
        ready, _, _ = select.select([sys.stdin], [], [], TICK_S)
        if ready:
            chunk = os.read(sys.stdin.fileno(), 64)
            if not chunk:
                return 0
            events, pending = parse_input(pending + chunk, final=False)
        else:
            events, pending = parse_input(pending, final=True)
        # A focus report is not a key: only a key closes this.
        if any(ev in ("q", "Q", ESCAPE, ENTER) for ev in events):
            return 0


# ── snapshot: a view as text ────────────────────────────────────────

# How long a snapshot waits for its fetches. fleet.py bounds each source;
# this bounds the whole, and a section still being read when it passes is
# printed as the pane draws one: `…`, and `reading <section>` in the
# status line.
SNAPSHOT_WAIT_S = 120.0
# The width when stdout is no terminal (an agent's shell): every column the
# board has, so nothing is cut that the owner's wide pane would show.
SNAPSHOT_WIDTH = 200
SNAPSHOT_USAGE = ("usage: snapshot board | agent LOGIN | compare [--metric 1-6] | plan | prs  "
                  "[--width N]")


class SnapshotError(Exception):
    """The data a snapshot needs could not be read: one line, exit 1."""


def collect(view: View, store: Store, results: "queue.Queue[Result]", wait_s: float,
            clock: Callable[[], float] = time.monotonic) -> list[str]:
    """Fetch each of the view's sections once and put what comes back in
    the store, as the pane does at open. The whys of the sections whose
    fetch failed whole, in the order they came."""
    view.tick(focused=None)       # at open: every section once, whatever the focus
    failures: list[str] = []
    deadline = clock() + wait_s
    while view.refresher.running:
        left = deadline - clock()
        if left <= 0:
            break
        try:
            r = results.get(timeout=left)
        except queue.Empty:
            break
        store.put(r.section, r.records)
        for section, records in r.extra.items():
            store.put(section, records)
        store.fetched = store.fetched or not r.why
        view.take(r)
        if r.why:
            failures.append(f"{r.section}: {r.why}")
    return failures


def snapshot_lines(fleet, screen: str, login: str | None, width: int, metric: int = 0,
                   ascii_only: bool = False, wait_s: float = SNAPSHOT_WAIT_S) -> list[vr.Line]:
    """One screen as the pane draws it, read afresh, every row shown.
    SnapshotError when the registry cannot be read, or every section it
    fetched failed: there is nothing of the fleet to print."""
    try:
        placements = fleet.load_placements(fleet.roots.engine_root())
    except Exception as e:  # noqa: BLE001 — said in one line, never a traceback
        raise SnapshotError(f"the hosts registry could not be read: {e}") from e
    if screen == "agent" and login not in placements:
        raise LookupError(f"{login} is not a placed agent (runtime/hosts/registry.json)")
    store = Store()
    results: "queue.Queue[Result]" = queue.Queue()
    sections = vr.AGENT_SECTIONS if screen == "agent" else SCREEN_SECTIONS[screen]
    view = View(fleet, sections, login if screen == "agent" else None, store, results)
    view.snapshot = True
    asked = set(view.refresher.ttl)
    failures = collect(view, store, results, wait_s)
    # Read is what answered without failing: a section still being read
    # at the wait is no more read than one that failed.
    pending = sorted(view.refresher.running)
    if asked and len(failures) + len(pending) == len(asked):
        parts = ([f"still reading after {wait_s:.0f} s: {', '.join(pending)}"] if pending else []) + failures[:1]
        raise SnapshotError("no section could be read; " + "; ".join(parts))
    if screen == "agent":
        a = agents_of({login: placements[login]}, store, view.sections, view.whys, fleet)[0]
        samples = vr.Samples()
        samples.add(store.get("proc", login))
        # The Enter view, as it opens over the board: its keys are the board's.
        return vr.agent_lines(a, samples, status(view, [a], None, store), 0, width, None,
                              vr.AGENT_KEYS, ascii_only)[0]
    return screen_lines(Nav(screen, metric=metric), view, placements, store, None, width, None, ascii_only)


def snapshot_text(lines: list[vr.Line]) -> str:
    """The lines as plain text: every state the pane colours has its word
    or mark beside it, so dropping the styles drops no meaning."""
    return "".join(vr.line_text(line).rstrip() + "\n" for line in lines)


def snapshot_main(args: list[str], env: dict[str, str] | None = None) -> int:
    """`snapshot <view> …`: print one view as text and exit, for an agent to
    read what the owner sees. Opens no pane and reads no herdr socket, so
    it runs inside one too."""
    import argparse  # noqa: PLC0415

    env = dict(os.environ) if env is None else env
    parser = argparse.ArgumentParser(
        prog="snapshot", usage=SNAPSHOT_USAGE.removeprefix("usage: "),
        description="Print one Fleet Deck view as text, read afresh, every row shown. "
        "Exit 0 with the view, 1 when the fleet's data cannot be read, 2 on usage.")
    parser.add_argument("view", choices=["board", "agent", "compare", "plan", "prs"])
    parser.add_argument("login", nargs="?", help="agent only: the agent's login")
    parser.add_argument("--metric", type=int, choices=range(1, len(rr.METRICS) + 1), default=1,
                        metavar="1-6", help="compare only: " + rr.metric_list(-1).strip())
    parser.add_argument("--width", type=int, help=f"columns (default: the terminal's, else {SNAPSHOT_WIDTH})")
    a = parser.parse_args(args)
    if (a.view == "agent") != (a.login is not None):
        parser.error("a login goes with agent, and only with it")
    if a.width is not None and a.width < 20:
        parser.error("--width is at least 20")
    width = a.width or (os.get_terminal_size(sys.stdout.fileno()).columns
                        if sys.stdout.isatty() else SNAPSHOT_WIDTH)
    root = fabric_root(env)
    if root is None:
        print("snapshot: agent-fabric not found: set AGENT_FABRIC_ROOT, or put fabric-ctl on PATH", file=sys.stderr)
        return 1
    try:
        fleet = import_fleet(root)
    except Exception as e:  # noqa: BLE001 — a fleet.py that fails to load is one line, never a traceback
        print(f"snapshot: agent-fabric's fleet.py could not be loaded: {vr.clean(f'{type(e).__name__}: {e}')}",
              file=sys.stderr)
        return 1
    try:
        lines = snapshot_lines(fleet, a.view, a.login, width, a.metric - 1,
                               ascii_only="utf" not in (sys.stdout.encoding or "").lower())
    except LookupError as e:
        print(f"snapshot: {e}", file=sys.stderr)
        return 2
    except SnapshotError as e:
        print(f"snapshot: {vr.clean(str(e))}", file=sys.stderr)
        return 1
    sys.stdout.write(snapshot_text(lines))
    return 0


# ── the commands ────────────────────────────────────────────────────

USAGE = ("usage: fabric-view board | agent [--agent LOGIN [--in-tab]] | prs | snapshot VIEW … "
         "| open board|agent|prs|stop | toggle")


def plugin_context(env: dict[str, str]) -> dict:
    try:
        ctx = json.loads(env.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
    except ValueError:
        return {}
    return ctx if isinstance(ctx, dict) else {}


def tab_roles(panes: list[dict], tab_id: str | None) -> dict[str, str]:
    """The tab's panes by the role the deck labelled them with: the last of
    each label, as read_tab takes it, so a label a person repeated names
    the same pane to the toggle as to the deck."""
    roles: dict[str, str] = {}
    for pane in panes:
        label = pane.get("label")
        if tab_id is not None and pane.get("tab_id") == tab_id and isinstance(label, str):
            roles[label] = pane.get("pane_id")
    return roles


def toggle_step(roles: dict[str, str], focused: str | None) -> tuple[str, str] | None:
    """The zoom that turns the tab over: from the agent screen to the harness,
    from anywhere else in the tab to the agent screen. Both stay zoomed: the
    tab shows one pane at a time, the one its second row marks
    (ui.pane_tabs), and herdr's zoom focuses the pane it names. None for a
    tab without both panes: not one the deck keeps."""
    harness, agent = roles.get(HARNESS), roles.get(AGENT)
    if not harness or not agent:
        return None
    return (harness, "--on") if focused == agent else (agent, "--on")


# Where view_lock is taken, for a test only; never set on a host.
LOCK_DIR_ENV = "FABRIC_DECK_LOCK_DIR"


def toggle(env: dict[str, str], herdr, sleep: Callable[[float], None] = time.sleep) -> int:
    """A plugin action's command: one chord, the account tab between its
    harness and its agent screen. The harness's session runs on in its
    pane; only the zoom and the focus change. In a tab without an agent
    pane (one the deck has not restored yet), the agent's overlay, as
    before the pane existed, and the same chord closes it. Each press acts
    under view_lock on the tab as it is then, its focus read from the pane
    list, never from the context captured at the key, which a press still
    running may have made stale."""
    ctx = plugin_context(env)
    tab = ctx.get("tab_id")
    with view_lock(env.get(LOCK_DIR_ENV)):
        panes = herdr.call("pane", "list").get("panes", [])
        if left_tab(panes, tab):
            # The person has left the tab the press was made in (presses
            # queued, then another tab): FleetDeck would open an overlay in
            # the tab shown now, which no press here was about.
            return 0
        focused = next((p.get("pane_id") for p in panes if p.get("focused") is True and p.get("tab_id") == tab),
                       ctx.get("focused_pane_id"))
        roles = tab_roles(panes, tab)
        step = toggle_step(roles, focused)
        if step is None:
            # Known by what runs in it, never by its label: a person may set
            # "this agent" on any pane, and the close ends what runs there.
            overlays = [p.get("pane_id") for p in panes
                        if tab is not None and p.get("tab_id") == tab and any(
                            is_overlay_view(fp.get("argv") or [])
                            for fp in herdr.process_info(p.get("pane_id")).get("foreground_processes") or [])]
            closed = []
            for overlay in overlays:
                try:
                    herdr.call("plugin", "pane", "close", overlay)
                    closed.append(overlay)
                except DeckError as error:
                    # Only a pane herdr says is no plugin pane (a person's own
                    # view, or a label set by hand) is passed over. Any other
                    # failure is raised: opening another overlay beside one
                    # that would not close is the stacking this refuses.
                    if "plugin_pane_not_found" not in str(error):
                        raise
                    print(f"fabric-view toggle: {overlay} is no overlay to close: {error}", file=sys.stderr)
            # Opened before the lock is let go, so the next press finds it.
            return 0 if closed else open_overlay(env)
        return _turn(ctx, herdr, step, roles.get(AGENT), sleep)


def left_tab(panes: list[dict], tab: str | None) -> bool:
    """Whether the person is now in another tab than `tab`: FleetDeck marks
    one pane focused, the active tab's."""
    return any(p.get("focused") is True for p in panes) and \
        not any(p.get("focused") is True and p.get("tab_id") == tab for p in panes)


def _turn(ctx: dict, herdr, step: tuple[str, str], agent: str | None,
          sleep: Callable[[float], None]) -> int:
    pane, zoom = step
    login = ctx.get("tab_label")
    if pane != agent or not isinstance(login, str) or not SAFE_LOGIN.match(login):
        herdr.call("pane", "zoom", pane, zoom)
        return 0
    info = herdr.process_info(pane)
    if at_bare_shell(info):
        # The view ended (or never started): started again where the person
        # is about to look, in the operator's own shell there. Zoomed first,
        # so it starts at the size it is seen at; the zoom focuses the pane
        # before the view turns focus reporting on, so no focus-in reaches
        # it: start_view tells it its focus once it can hear (on a timeout
        # it waits for a key), and the lock is held until then, so the next
        # press's focus change reaches it.
        herdr.call("pane", "zoom", pane, zoom)
        start_view(herdr, pane, login, True, sleep)
        return 0
    view = next((p for p in info.get("foreground_processes") or []
                 if is_agent_view(p.get("argv") or [], login) and isinstance(p.get("pid"), int)), None)
    if view is not None:
        # This login's view, which the deck may have started a moment ago:
        # focus moved onto it before it turns focus reporting on is dropped,
        # and it would wait for a key before its first fetch. Its own start's
        # title is waited for, bounded; anything else in the pane is zoomed
        # at once.
        if not wait_ready(herdr, pane, login, sleep, view_mark(view["pid"])):
            # Shown anyway: a chord that shows nothing reads as broken. Said
            # in the plugin's log; the screen fetches at its first key.
            print(f"fabric-view toggle: {login}'s agent screen in {pane} did not report ready "
                  "within the bound; shown, and it fetches at the first key", file=sys.stderr)
        if left_tab(herdr.call("pane", "list").get("panes", []), ctx.get("tab_id")):
            # The person went elsewhere while the view came up: the zoom
            # would focus this pane and take them back to the tab they left.
            return 0
    herdr.call("pane", "zoom", pane, zoom)
    return 0


def open_overlay(env: dict[str, str]) -> int:
    """The agent's overlay, opened and waited for: the toggle holds its lock
    until FleetDeck has the pane, where `open` hands its process over. Bound
    as every other herdr call is (Herdr.text): a server that never answers
    must not hold every later press at the lock."""
    herdr = env.get("HERDR_BIN_PATH") or shutil.which(BIN)
    if not herdr:
        print("fabric-view: no agent-fabric-fleetdeck to ask (HERDR_BIN_PATH is not set)", file=sys.stderr)
        return 2
    try:
        return subprocess.run(open_argv(herdr, env.get("HERDR_PLUGIN_ID") or PLUGIN_ID, "agent"),
                              stdout=subprocess.DEVNULL, timeout=OPEN_TIMEOUT_S).returncode
    except subprocess.TimeoutExpired:
        print(f"fabric-view: FleetDeck did not open the overlay within {OPEN_TIMEOUT_S} s", file=sys.stderr)
        return 1


OPEN_TIMEOUT_S = 30


def open_pane(entrypoint: str, env: dict[str, str]) -> int:
    """A plugin action's command: open the entrypoint's pane. The pane then
    runs with its own context, so the overlay learns the tab it covers."""
    herdr = env.get("HERDR_BIN_PATH") or shutil.which("agent-fabric-fleetdeck")
    if not herdr:
        print("fabric-view: no agent-fabric-fleetdeck to ask (HERDR_BIN_PATH is not set)", file=sys.stderr)
        return 2
    plugin = env.get("HERDR_PLUGIN_ID") or PLUGIN_ID
    # --focus: the person pressed a key to see this view. herdr focuses the
    # pane before the view turns focus reporting on, so no focus-in reaches
    # it; the view is told instead.
    os.execv(herdr, open_argv(herdr, plugin, entrypoint))
    return 0   # not reached


# A popup's size: rows of PRs read best wide, and the tab stays visible
# around it, so the person knows where Esc returns them.
POPUP_SIZE = {"prs": ("80%", "80%"), "stop": ("70%", "40%")}


def open_argv(herdr: str, plugin: str, entrypoint: str) -> list[str]:
    argv = [herdr, "plugin", "pane", "open", "--plugin", plugin, "--entrypoint", entrypoint]
    if entrypoint in POPUP_SIZE:
        w, h = POPUP_SIZE[entrypoint]
        argv += ["--width", w, "--height", h]
    return argv + ["--focus", "--env", f"{OPENED_FOCUSED}=1"]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE, file=sys.stderr if not args else sys.stdout)
        return 0 if args else 2
    mode, rest = args[0], args[1:]
    if mode == "snapshot":
        return snapshot_main(rest)
    if mode == "open":
        if rest not in (["board"], ["agent"], ["prs"], ["stop"]):
            print(USAGE, file=sys.stderr)
            return 2
        return open_pane(rest[0], dict(os.environ))
    if mode == "toggle" and not rest:
        env = dict(os.environ)
        try:
            return toggle(env, Herdr(binary=env.get("HERDR_BIN_PATH") or shutil.which(BIN) or BIN))
        except Exception as e:  # noqa: BLE001 — herdr's refusal, said in the plugin's log
            print(f"fabric-view toggle: {e}", file=sys.stderr)
            return 1
    if mode not in ("board", "agent", "prs"):
        print(USAGE, file=sys.stderr)
        return 2
    login = None
    in_tab = False
    if mode == "agent":
        if rest[:1] == ["--agent"] and len(rest) == 2:
            login = rest[1]
        elif rest[:1] == ["--agent"] and rest[2:] == ["--in-tab"]:
            login, in_tab = rest[1], True
        elif rest:
            print(USAGE, file=sys.stderr)
            return 2
        else:
            login = context_login(dict(os.environ))
    elif rest:
        print(USAGE, file=sys.stderr)
        return 2
    root = fabric_root(dict(os.environ))
    if root is None:
        print("fabric-view: agent-fabric not found: set AGENT_FABRIC_ROOT, or put fabric-ctl on PATH", file=sys.stderr)
        return 2
    try:
        fleet = import_fleet(root)
    except ImportError as e:
        print(f"fabric-view: {e}", file=sys.stderr)
        return 2

    import curses  # noqa: PLC0415 — `open` and the refusals above need no terminal
    os.environ.setdefault("ESCDELAY", "25")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        return curses.wrapper(lambda screen: run(curses, screen, fleet, mode, login, in_tab))
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write(closing(in_tab))
        sys.stdout.flush()


def initial_focus(env) -> bool | None:
    """A view's focus before any report: True for an overlay `open` focused,
    unknown otherwise, and unknown for a marked view whatever it is told,
    which its start reports once it can hear (fabric_deck.start_view)."""
    return True if env.get(OPENED_FOCUSED) == "1" and not env.get(VIEW_START) else None


def in_tab_title(login: str | None, env) -> str | None:
    """The title an in-tab view sets once it hears focus: its start's own
    (fabric_deck.view_title), the sign the deck and the toggle wait for."""
    return view_title(login, env.get(VIEW_START)) if login else None


def closing(in_tab: bool) -> str:
    """What a view writes as it ends: focus reporting off, and in the tab its
    title cleared. Left set, the title would read as the next view in the
    pane ready before that view can hear focus (fabric_deck.view_ready)."""
    return FOCUS_OFF + ("\x1b]2;\x07" if in_tab else "")
