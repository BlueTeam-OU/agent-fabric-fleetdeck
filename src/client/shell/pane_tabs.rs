//! The second tab row. A tab whose panes carry exactly the labels in
//! `ui.pane_tabs` shows one pane at a time, and this row picks which.
//!
//! The row keeps no state of its own: the pane it marks is the server's zoom,
//! a zoomed tab and its focused pane. Picking sends the zoom request the zoom
//! key sends, aimed at that pane, so any endpoint serves it, and whoever else
//! zooms a pane (the fleet deck, another client) moves the mark with it.

use super::*;

use super::render::{display_width, put_text};
use crate::api::schema::{Method, PaneZoomMode, PaneZoomParams};
use crate::config::IndexedKeybind;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct PaneTab<'a> {
    pub(super) label: &'a str,
    pub(super) pane_id: &'a str,
    pub(super) selected: bool,
}

/// The shown tab's panes in `labels` order, when its panes carry exactly those
/// labels, each once. A tab with any other pane, or a label missing or doubled,
/// shows its panes as they are laid out.
pub(super) fn pane_tab_row<'a>(
    snapshot: &'a ClientShellSnapshot,
    labels: &'a [String],
) -> Option<Vec<PaneTab<'a>>> {
    if labels.is_empty() {
        return None;
    }
    let tab_id = snapshot.focused_tab_id.as_deref()?;
    let tab = snapshot.tabs.iter().find(|tab| tab.tab_id == tab_id)?;
    let in_tab = || {
        snapshot
            .panes
            .iter()
            .filter(move |pane| pane.tab_id == tab_id)
    };
    if in_tab().count() != labels.len() {
        return None;
    }
    labels
        .iter()
        .map(|label| {
            let mut carrying = in_tab().filter(|pane| pane.label.as_deref() == Some(label));
            let pane = carrying.next()?;
            if carrying.next().is_some() {
                return None;
            }
            Some(PaneTab {
                label,
                pane_id: &pane.pane_id,
                selected: tab.zoomed
                    && snapshot.focused_pane_id.as_deref() == Some(pane.pane_id.as_str()),
            })
        })
        .collect()
}

/// Zooming a pane focuses it (`AppState::apply_pane_zoom`), and a tab already
/// zoomed stays zoomed on the newly focused pane: one request picks it.
pub(super) fn pick_pane_tab(pane_id: &str) -> Method {
    Method::PaneZoom(PaneZoomParams {
        pane_id: Some(pane_id.to_string()),
        mode: PaneZoomMode::On,
    })
}

// Dark text on the yellow row reads in light and dark themes alike; a theme's
// panel colour is light in a light theme. An indexed yellow pairs with the
// indexed black of the same terminal palette.
fn on_yellow(palette: &Palette) -> ratatui::style::Color {
    match palette.yellow {
        ratatui::style::Color::Rgb(..) => ratatui::style::Color::Rgb(0, 0, 0),
        _ => ratatui::style::Color::Black,
    }
}

/// The key after the prefix that picks each cell (`keys.select_pane_tab`), the
/// first binding of each index, as the row names it: "F1", not "prefix+f1".
/// A cell no binding picks names no key, so the row never teaches a key that
/// does something else (the digits after the prefix switch tabs).
pub(super) fn pane_tab_keys(bindings: &[IndexedKeybind], cells: usize) -> Vec<Option<String>> {
    let mut keys = vec![None; cells];
    for binding in bindings {
        let Some(slot) = binding.index().and_then(|index| keys.get_mut(index)) else {
            continue;
        };
        if slot.is_none() {
            let key = binding
                .label
                .strip_prefix("prefix+")
                .unwrap_or(&binding.label);
            *slot = Some(match key.strip_prefix('f') {
                Some(number) if number.chars().all(|c| c.is_ascii_digit()) => format!("F{number}"),
                _ => key.to_string(),
            });
        }
    }
    keys
}

/// What each cell says, the fullest form whose cells all fit `width` whole:
/// key and name ("F1 harness"), the name alone, then the key alone (the
/// name's first letter where no key picks it). Every cell keeps its place,
/// its click and its mark at any width; a cell is never cut.
fn pane_tab_cells(row: &[PaneTab<'_>], keys: &[Option<String>], width: u16) -> Vec<String> {
    let name = |form: u8, index: usize, tab: &PaneTab<'_>| {
        let key = keys.get(index).and_then(Option::as_deref);
        match (form, key) {
            (0, Some(key)) => format!("{key} {}", tab.label),
            (0 | 1, _) => tab.label.to_string(),
            (_, Some(key)) => key.to_string(),
            (_, None) => tab
                .label
                .chars()
                .next()
                .map(String::from)
                .unwrap_or_default(),
        }
    };
    let mut names = Vec::new();
    for form in 0..3 {
        names = row
            .iter()
            .enumerate()
            .map(|(index, tab)| name(form, index, tab))
            .collect();
        // Each cell is its name padded or bracketed by one on each side, one
        // column between cells.
        let needed: usize = names
            .iter()
            .map(|name| usize::from(display_width(name)) + 2)
            .sum::<usize>()
            + names.len().saturating_sub(1);
        if needed <= usize::from(width) {
            break;
        }
    }
    names
}

/// One cell per pane. The picked one is drawn inverted, bold and in
/// brackets, so the mark does not rest on colour alone; brackets and padding
/// are the same width, so picking moves nothing.
pub(super) fn render_pane_tab_row(
    buffer: &mut Buffer,
    area: Rect,
    row: &[PaneTab<'_>],
    keys: &[Option<String>],
    palette: &Palette,
    hits: &mut ShellHitMap,
) {
    let dark = on_yellow(palette);
    let plain = Style::default().fg(dark).bg(palette.yellow);
    let picked = Style::default()
        .fg(palette.yellow)
        .bg(dark)
        .add_modifier(Modifier::BOLD);
    buffer.set_style(area, plain);
    let mut x = area.x;
    for (tab, name) in row.iter().zip(pane_tab_cells(row, keys, area.width)) {
        let (text, style) = if tab.selected {
            (format!("[{name}]"), picked)
        } else {
            (format!(" {name} "), plain)
        };
        // Past the shortest form (a window narrower than four key cells) a
        // cell is cut at the edge rather than dropped.
        let width = display_width(&text).min(area.right().saturating_sub(x));
        if width == 0 {
            break;
        }
        put_text(buffer, x, area.y, width, &text, style);
        hits.pane_tabs
            .push((Rect::new(x, area.y, width, 1), tab.pane_id.to_string()));
        x = x.saturating_add(width).saturating_add(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::ClientShellPane;

    fn snapshot(zoomed: bool, focused: &str, labels: &[Option<&str>]) -> ClientShellSnapshot {
        let mut snapshot = crate::client::shell::tests::snapshot();
        snapshot.focused_tab_id = Some("t1".into());
        snapshot.focused_pane_id = Some(focused.into());
        snapshot.tabs = vec![ClientShellTab {
            tab_id: "t1".into(),
            workspace_id: "w1".into(),
            number: 1,
            label: "acct".into(),
            custom_label: true,
            zoomed,
            focused: true,
            agent_status: crate::api::schema::AgentStatus::Unknown,
        }];
        snapshot.panes = labels
            .iter()
            .enumerate()
            .map(|(index, label)| ClientShellPane {
                pane_id: format!("p{index}"),
                workspace_id: "w1".into(),
                tab_id: "t1".into(),
                label: label.map(String::from),
                cwd: None,
                foreground_cwd: None,
                focused: focused == format!("p{index}"),
                right_click_passthrough: false,
            })
            .collect();
        snapshot
    }

    fn labels() -> Vec<String> {
        ["harness", "shell", "status", "agent"]
            .map(String::from)
            .to_vec()
    }

    #[test]
    fn row_follows_configured_order_and_marks_the_zoomed_focused_pane() {
        let snapshot = snapshot(
            true,
            "p1",
            &[
                Some("agent"),
                Some("harness"),
                Some("status"),
                Some("shell"),
            ],
        );
        let labels = labels();
        let row = pane_tab_row(&snapshot, &labels).expect("an account tab shows the row");
        let picked: Vec<_> = row
            .iter()
            .map(|tab| (tab.label, tab.pane_id, tab.selected))
            .collect();
        assert_eq!(
            picked,
            [
                ("harness", "p1", true),
                ("shell", "p3", false),
                ("status", "p2", false),
                ("agent", "p0", false),
            ]
        );
    }

    #[test]
    fn an_unzoomed_tab_marks_no_pane() {
        let snapshot = snapshot(
            false,
            "p0",
            &[
                Some("harness"),
                Some("shell"),
                Some("status"),
                Some("agent"),
            ],
        );
        let labels = labels();
        let row = pane_tab_row(&snapshot, &labels).expect("the row stays while unzoomed");
        assert!(row.iter().all(|tab| !tab.selected));
    }

    #[test]
    fn other_tabs_show_no_row() {
        let labels = labels();
        for panes in [
            // A hand-made tab.
            vec![Some("harness"), None],
            // One more pane than the row has cells.
            vec![
                Some("harness"),
                Some("shell"),
                Some("status"),
                Some("agent"),
                None,
            ],
            // A label doubled, another missing.
            vec![
                Some("harness"),
                Some("harness"),
                Some("status"),
                Some("agent"),
            ],
            // A label nobody configured.
            vec![
                Some("harness"),
                Some("shell"),
                Some("status"),
                Some("this agent"),
            ],
        ] {
            let snapshot = snapshot(true, "p0", &panes);
            assert_eq!(pane_tab_row(&snapshot, &labels), None, "{panes:?}");
        }
        let snapshot = snapshot(
            true,
            "p0",
            &[
                Some("harness"),
                Some("shell"),
                Some("status"),
                Some("agent"),
            ],
        );
        assert_eq!(
            pane_tab_row(&snapshot, &[]),
            None,
            "an empty list turns the row off"
        );
    }

    fn account_tab(focused: &str) -> ClientShellSnapshot {
        snapshot(
            true,
            focused,
            &[
                Some("harness"),
                Some("shell"),
                Some("status"),
                Some("agent"),
            ],
        )
    }

    #[test]
    fn each_cell_names_the_key_that_picks_it() {
        let config = crate::config::Config::default();
        let keys = pane_tab_keys(&config.keybinds().select_pane_tab, 4);
        assert_eq!(
            keys,
            ["F1", "F2", "F3", "F4"].map(|key| Some(key.to_string()))
        );
        assert_eq!(
            pane_tab_keys(&[], 4),
            vec![None; 4],
            "no binding, no key named"
        );
    }

    #[test]
    fn the_rendered_row_marks_the_shown_pane_and_a_click_finds_its_pane() {
        let config = crate::config::Config::default();
        let palette = crate::app::client_palette_from_config(&config);
        let snapshot = account_tab("p2");
        let labels = labels();
        let row = pane_tab_row(&snapshot, &labels).expect("an account tab shows the row");
        let keys = pane_tab_keys(&config.keybinds().select_pane_tab, row.len());
        let area = Rect::new(0, 0, 60, 1);
        let mut buffer = Buffer::empty(area);
        let mut hits = ShellHitMap::default();
        render_pane_tab_row(&mut buffer, area, &row, &keys, &palette, &mut hits);

        let text: String = (0..area.width)
            .map(|x| buffer[(x, 0)].symbol().to_string())
            .collect();
        assert_eq!(
            text.trim_end(),
            " F1 harness   F2 shell  [F3 status]  F4 agent"
        );
        let status = text.find("[F3").expect("the mark") as u16;
        assert!(buffer[(status, 0)].modifier.contains(Modifier::BOLD));
        assert_eq!(buffer[(status, 0)].bg, on_yellow(&palette), "inverted");
        assert_eq!(buffer[(1, 0)].bg, palette.yellow);

        let clicked = hits
            .pane_tabs
            .iter()
            .find(|(rect, _)| {
                crate::client::shell::contains(*rect, (text.find("agent").unwrap() as u16, 0))
            })
            .map(|(_, pane)| pane.as_str());
        assert_eq!(clicked, Some("p3"), "a click on agent picks the agent pane");
        assert_eq!(
            pick_pane_tab("p3"),
            Method::PaneZoom(PaneZoomParams {
                pane_id: Some("p3".into()),
                mode: PaneZoomMode::On,
            })
        );
    }

    #[test]
    fn a_narrow_row_keeps_every_cell_whole_and_the_mark() {
        let config = crate::config::Config::default();
        let palette = crate::app::client_palette_from_config(&config);
        let snapshot = account_tab("p3");
        let labels = labels();
        let row = pane_tab_row(&snapshot, &labels).expect("an account tab shows the row");
        let keys = pane_tab_keys(&config.keybinds().select_pane_tab, row.len());
        for (width, expected) in [
            (35, " harness   shell   status  [agent]"),
            (20, " F1   F2   F3  [F4]"),
        ] {
            let area = Rect::new(0, 0, width, 1);
            let mut buffer = Buffer::empty(area);
            let mut hits = ShellHitMap::default();
            render_pane_tab_row(&mut buffer, area, &row, &keys, &palette, &mut hits);
            let text: String = (0..width)
                .map(|x| buffer[(x, 0)].symbol().to_string())
                .collect();
            assert_eq!(text.trim_end(), expected, "{width} columns");
            assert_eq!(hits.pane_tabs.len(), 4, "{width}: every cell is clickable");
            assert!(hits.pane_tabs.iter().all(|(rect, _)| rect.right() <= width));
            assert_eq!(hits.pane_tabs[3].1, "p3");
        }
    }
}
