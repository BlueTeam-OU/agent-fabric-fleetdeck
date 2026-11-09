---
role: "rust-ui-dev"
class: solution
topic: "attach-pane-scroll-bar"
description: "Why a deck pane running `terminal attach` (moveto --attach) had no scroll bar, how j189 / PR #57 restores it, and how to check it live"
tier: 2
knowledge_scope: full
distilled_at: "2026-11-08"
origin:
  - agent: "rust-ui-dev-01"
    host: "develop-qzapp"
    project: herdr
    working_copy: herdr
derived_from:
  - c8786ce1df2fdb1c
---

## Why a deck pane running `terminal attach` (moveto --attach) had no scroll bar, how j189 / PR #57 restores it, and how to check it live

Before PR #57, a FleetDeck direct terminal attach (`terminal attach <term>`, which the operator deck's `moveto --attach` harness panes run) showed no scroll bar, from the first moment of the attach. A fresh session did not cause it. The causes:
- `setup_direct_attach_terminal` calls `ratatui::init`, which puts the deck pane's own terminal on the alternate screen. The deck draws a pane bar only on the main screen with scrollback (`ui/panes.rs` `stable_scrollbar_gutter`).
- The server sent the attach only `render_terminal_virtual` cells, with no bar.

The fix (j189, PR #57, head f982cd93): `server/terminal_attach.rs` `attach_layout` applies the pane gutter rule to the attach client's area. The attach frame draws `render_pane_scrollbar_buffer` in the gutter. The owner's grid is resized at attach, at client resize and at each frame (the gutter goes on the alternate screen). `attach_scrollbar_drag` copies the shell's press/drag/release behaviour. Pixel mouse maps to the grid.
- The attached grid is one column narrower on the main screen: tests that pin attach widths change (100 -> 99, 800 -> 792 px).

Live check without the owner's deck: two throwaway `--session` servers. The outer pane runs `<bin> --session inner terminal attach <tid>`.
- `pane read` on the outer pane shows ▕/▐ in the last column.
- `pane send-text` of SGR mouse (`\e[<0;COL;ROWM`, drag `\e[<32;...M`) drives the bar. Check the inner offset with `pane get`.
- Unset every HERDR_* in the env first.

Related: [[herdr-host-toolchain]], [[j167-fleetdeck-focus-baseline]]

#57 merged on 2026-11-01 at head 102134e2 (1 work, 8 fix; master 4dbda937), after seven blind review rounds. Rules the reviews added, which belong to any direct-attach pointer work:
- The bar is per connection (`attach_scroll_bar`): `terminal attach` sets it, `session control` does not, and an observer follows its owner.
- A drag or release reaches the program only for a button whose press it was sent (`attach_program_held` bitmask). The bit is set only after the write succeeds and only while mouse reporting is on; any release clears it.
- Routing width is `min(grid, runtime cols)`: for one frame after the alternate screen toggles, the two differ by the gutter.
- Still open (pre-existing): a direct attach that goes away while holding a button never sends the program a release. The held mask would make the fix a few lines.

*References: herdr-host-toolchain, j167-fleetdeck-focus-baseline*

*Anchors: `src/server/terminal_attach.rs::attach_layout`, `src/server/terminal_attach.rs::attach_scrollbar_drag`, `src/client/terminal_setup.rs::setup_direct_attach_terminal`*

*Observed 2026-11-01 (rust-ui-dev)*
