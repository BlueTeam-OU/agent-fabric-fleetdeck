pub(crate) fn paste_payload_for_runtime(
    runtime: &crate::terminal::TerminalRuntime,
    text: &str,
) -> String {
    if runtime.bracketed_paste_enabled() {
        format!("\x1b[200~{text}\x1b[201~")
    } else {
        text.to_owned()
    }
}

/// Where an attached terminal's grid and its scroll bar track sit in a direct attach client's
/// `cols` x `rows`. The client hands the server its whole host terminal, so the pane's own
/// last-column scroll bar would otherwise vanish: a deck pane that attaches to an agent puts
/// its host terminal on the alternate screen, where the deck draws no bar of its own. The rule
/// is the pane's (`crate::ui::stable_scrollbar_gutter`): main screen only, and a track only when
/// there is scrollback.
pub(crate) fn attach_layout(
    runtime: &crate::terminal::TerminalRuntime,
    cols: u16,
    rows: u16,
    pane_scrollbars: bool,
) -> (ratatui::layout::Rect, Option<ratatui::layout::Rect>) {
    crate::ui::stable_scrollbar_gutter(
        runtime,
        ratatui::layout::Rect::new(0, 0, cols, rows),
        pane_scrollbars,
    )
}

/// Applies a direct attach client's pointer event to the attached terminal's scroll bar, as the
/// shell's pane scroll bar takes it: a left press on the thumb grabs it, a press elsewhere on the
/// track jumps there, a drag follows the pointer even off the track, a release ends it.
/// `Some(next grab)` when the bar took the event; `None` when it did not.
pub(crate) fn attach_scrollbar_drag(
    runtime: &crate::terminal::TerminalRuntime,
    track: Option<ratatui::layout::Rect>,
    grab: Option<u16>,
    kind: crate::protocol::ClientMouseKind,
    column: u16,
    row: u16,
) -> Option<Option<u16>> {
    use crate::protocol::{ClientMouseButton, ClientMouseKind};

    let on_track = track.filter(|track| column == track.x);
    match kind {
        ClientMouseKind::Down(ClientMouseButton::Left) if on_track.is_some() => {
            let (Some(track), Some(metrics)) = (on_track, runtime.scroll_metrics()) else {
                return Some(None);
            };
            let thumb_grab = crate::ui::scrollbar_thumb_grab_offset(metrics, track, row);
            if thumb_grab.is_none() {
                runtime.set_scroll_offset_from_bottom(crate::ui::scrollbar_offset_from_row(
                    metrics, track, row,
                ));
            }
            Some(thumb_grab)
        }
        ClientMouseKind::Drag(ClientMouseButton::Left) if grab.is_some() => {
            // The track can vanish mid-drag (the terminal entered its alternate screen): the
            // drag still ends at the release, and moves nothing meanwhile.
            if let (Some(track), Some(metrics), Some(grab)) =
                (track, runtime.scroll_metrics(), grab)
            {
                runtime.set_scroll_offset_from_bottom(crate::ui::scrollbar_offset_from_drag_row(
                    metrics, track, row, grab,
                ));
            }
            Some(grab)
        }
        ClientMouseKind::Up(ClientMouseButton::Left) if grab.is_some() => Some(None),
        // Everything else is the grid's or the gutter's (gutter_route), track or no track.
        _ => None,
    }
}

/// Where a pointer event off the scroll bar goes. `cells` is the width both the layout's grid and
/// the runtime agree on: for one frame after the alternate screen toggles they differ by the
/// gutter, and an event past either lands on no cell of the program. A drag or release goes to
/// the program only for a button whose press it was sent, wherever the pointer is, as the
/// shell's pane gesture does; a press the bar or the gutter took is not the program's.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum GutterRoute {
    /// Inside the cells: the attached terminal takes it as it is.
    Terminal,
    /// A held button's drag or release past the cells: the program gets it at its last column,
    /// or it would keep a button it never saw released.
    Clamp(u16),
    /// A drag or release of a button the program does not hold, or anything else past the cells.
    Drop,
}

/// The bit of `kind`'s button in a direct attach's record of the presses its program holds.
pub(crate) fn button_bit(kind: crate::protocol::ClientMouseKind) -> u8 {
    use crate::protocol::{ClientMouseButton, ClientMouseKind};

    match kind {
        ClientMouseKind::Down(button)
        | ClientMouseKind::Up(button)
        | ClientMouseKind::Drag(button) => match button {
            ClientMouseButton::Left => 1,
            ClientMouseButton::Right => 2,
            ClientMouseButton::Middle => 4,
        },
        _ => 0,
    }
}

/// `program_holds` says whether the program holds a press of this event's button.
pub(crate) fn gutter_route(
    kind: crate::protocol::ClientMouseKind,
    column: u16,
    cells: u16,
    program_holds: bool,
) -> GutterRoute {
    use crate::protocol::ClientMouseKind;

    let gesture = matches!(kind, ClientMouseKind::Drag(_) | ClientMouseKind::Up(_));
    if gesture && !program_holds {
        return GutterRoute::Drop;
    }
    if column < cells {
        return GutterRoute::Terminal;
    }
    match kind {
        _ if gesture && cells > 0 => GutterRoute::Clamp(cells - 1),
        _ => GutterRoute::Drop,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{ClientMouseButton, ClientMouseKind};
    use ratatui::layout::Rect;

    fn with_scrolled_runtime(test: impl FnOnce(&crate::terminal::TerminalRuntime)) {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("test runtime");
        let _guard = rt.enter();
        let mut bytes = Vec::new();
        for line in 0..80 {
            bytes.extend_from_slice(format!("line {line:02}\r\n").as_bytes());
        }
        let runtime =
            crate::terminal::TerminalRuntime::test_with_scrollback_bytes(20, 5, 4096, &bytes);
        test(&runtime);
        drop(runtime);
        drop(_guard);
        rt.shutdown_timeout(std::time::Duration::from_millis(100));
    }

    #[test]
    fn gutter_route_keeps_a_grid_press_released_over_the_gutter() {
        let left = ClientMouseButton::Left;
        assert_eq!(
            gutter_route(ClientMouseKind::Down(left), 79, 80, false),
            GutterRoute::Terminal
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Up(left), 80, 80, true),
            GutterRoute::Clamp(79)
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Drag(left), 80, 80, true),
            GutterRoute::Clamp(79)
        );
        // A press the program never saw (on the bar, or in the gutter) keeps its release, in
        // the gutter or back in the cells.
        assert_eq!(
            gutter_route(ClientMouseKind::Up(left), 10, 80, false),
            GutterRoute::Drop
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Drag(left), 10, 80, false),
            GutterRoute::Drop
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Up(left), 10, 80, true),
            GutterRoute::Terminal
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Moved, 10, 80, false),
            GutterRoute::Terminal
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Up(left), 80, 80, false),
            GutterRoute::Drop
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Drag(left), 80, 80, false),
            GutterRoute::Drop
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Down(left), 80, 80, true),
            GutterRoute::Drop
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Moved, 80, 80, true),
            GutterRoute::Drop
        );
        assert_eq!(
            gutter_route(ClientMouseKind::Up(left), 0, 0, true),
            GutterRoute::Drop
        );
    }

    #[test]
    fn button_bit_names_each_button_once() {
        let bits = [
            ClientMouseButton::Left,
            ClientMouseButton::Right,
            ClientMouseButton::Middle,
        ]
        .map(|button| button_bit(ClientMouseKind::Down(button)));
        assert_eq!(bits, [1, 2, 4]);
        assert_eq!(button_bit(ClientMouseKind::Up(ClientMouseButton::Right)), 2);
        assert_eq!(
            button_bit(ClientMouseKind::Drag(ClientMouseButton::Middle)),
            4
        );
        assert_eq!(button_bit(ClientMouseKind::Moved), 0);
    }

    #[test]
    fn attach_layout_keeps_the_panes_gutter_on_the_main_screen_only() {
        with_scrolled_runtime(|runtime| {
            let (grid, track) = attach_layout(runtime, 21, 5, true);
            assert_eq!(grid, Rect::new(0, 0, 20, 5));
            assert_eq!(track, Some(Rect::new(20, 0, 1, 5)));

            let (grid, track) = attach_layout(runtime, 21, 5, false);
            assert_eq!(grid, Rect::new(0, 0, 21, 5));
            assert_eq!(track, None);

            runtime.test_process_pty_bytes(b"\x1b[?1049h");
            let (grid, track) = attach_layout(runtime, 21, 5, true);
            assert_eq!(grid, Rect::new(0, 0, 21, 5));
            assert_eq!(track, None);
        });
    }

    #[test]
    fn attach_scrollbar_takes_press_drag_and_release_like_a_pane_bar() {
        with_scrolled_runtime(|runtime| {
            let track = Some(Rect::new(20, 0, 1, 5));
            let offset = || {
                runtime
                    .scroll_metrics()
                    .expect("metrics")
                    .offset_from_bottom
            };
            let max = runtime
                .scroll_metrics()
                .expect("metrics")
                .max_offset_from_bottom;
            assert!(max > 0);
            assert_eq!(offset(), 0);

            // Off the thumb (it sits at the bottom): jump to the top, no drag.
            let left = ClientMouseButton::Left;
            assert_eq!(
                attach_scrollbar_drag(runtime, track, None, ClientMouseKind::Down(left), 20, 0),
                Some(None)
            );
            assert_eq!(offset(), max);

            // On the thumb (now at the top): grab it without moving.
            let grab =
                attach_scrollbar_drag(runtime, track, None, ClientMouseKind::Down(left), 20, 0)
                    .expect("the bar takes a press on its thumb");
            assert_eq!(grab, Some(0));
            assert_eq!(offset(), max);

            // A drag follows the pointer even off the track; a release ends it.
            assert_eq!(
                attach_scrollbar_drag(runtime, track, grab, ClientMouseKind::Drag(left), 3, 4),
                Some(grab)
            );
            assert_eq!(offset(), 0);
            assert_eq!(
                attach_scrollbar_drag(runtime, track, grab, ClientMouseKind::Up(left), 3, 4),
                Some(None)
            );

            // The bar takes only its own left press, drag and release.
            assert_eq!(
                attach_scrollbar_drag(runtime, track, None, ClientMouseKind::Down(left), 3, 2),
                None
            );
            assert_eq!(
                attach_scrollbar_drag(runtime, track, None, ClientMouseKind::Drag(left), 3, 2),
                None
            );
            assert_eq!(
                attach_scrollbar_drag(
                    runtime,
                    track,
                    None,
                    ClientMouseKind::Down(ClientMouseButton::Right),
                    20,
                    2
                ),
                None
            );
            assert_eq!(
                attach_scrollbar_drag(runtime, None, None, ClientMouseKind::Down(left), 20, 2),
                None
            );
        });
    }
}
