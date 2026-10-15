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

/// One cell per pane, numbered as its key picks it. The picked one is drawn
/// inverted, bold and in brackets, so the mark does not rest on colour alone;
/// brackets and padding are the same width, so picking moves nothing.
pub(super) fn render_pane_tab_row(
    buffer: &mut Buffer,
    area: Rect,
    row: &[PaneTab<'_>],
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
    for (index, tab) in row.iter().enumerate() {
        let number = index + 1;
        let (text, style) = if tab.selected {
            (format!("[{number} {}]", tab.label), picked)
        } else {
            (format!(" {number} {} ", tab.label), plain)
        };
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
}
