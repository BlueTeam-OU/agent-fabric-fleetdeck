use std::collections::{BTreeMap, BTreeSet};

use serde::Deserialize;

/// The picked cell's colours in the second tab row, for one pane label
/// (`ui.pane_tab_colors.<label>`). An empty value takes the row-wide one.
#[derive(Debug, Clone, Default, PartialEq, Eq, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct PaneTabColorsConfig {
    pub selected_bg: String,
    pub selected_fg: String,
}

/// What is wrong with the second tab row's settings. Each wrong entry is
/// ignored, not the section: the row still shows, in `ui.pane_tabs` order.
pub(crate) fn pane_tabs_diagnostics(
    labels: &[String],
    orders: &BTreeMap<String, Vec<String>>,
    colors: &BTreeMap<String, PaneTabColorsConfig>,
) -> Vec<String> {
    let mut diagnostics = Vec::new();
    for (tab, order) in orders {
        if !is_pane_tab_order(labels, order) {
            diagnostics.push(format!(
                "ui.pane_tab_order.{tab:?} must list the labels of ui.pane_tabs, each once; \
                 that tab keeps the ui.pane_tabs order"
            ));
        }
    }
    for label in colors.keys() {
        if !labels.contains(label) {
            diagnostics.push(format!(
                "ui.pane_tab_colors.{label:?} names no label of ui.pane_tabs; it colours nothing"
            ));
        }
    }
    diagnostics
}

/// A tab's own order is the same labels as `ui.pane_tabs`, rearranged: a tab
/// qualifies for the row by carrying exactly those labels, so an order with
/// other labels would describe a row no tab can have.
pub(crate) fn is_pane_tab_order(labels: &[String], order: &[String]) -> bool {
    let wanted: BTreeSet<&String> = labels.iter().collect();
    let given: BTreeSet<&String> = order.iter().collect();
    order.len() == labels.len() && given.len() == order.len() && given == wanted
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strings(values: &[&str]) -> Vec<String> {
        values.iter().map(|value| value.to_string()).collect()
    }

    #[test]
    fn an_order_is_the_same_labels_rearranged() {
        let labels = strings(&["harness", "shell", "status", "agent"]);
        assert!(is_pane_tab_order(
            &labels,
            &strings(&["agent", "harness", "shell", "status"])
        ));
        for order in [
            strings(&["agent", "harness", "shell"]),
            strings(&["agent", "agent", "shell", "status"]),
            strings(&["agent", "harness", "shell", "status", "extra"]),
            strings(&["agent", "harness", "shell", "other"]),
        ] {
            assert!(!is_pane_tab_order(&labels, &order), "{order:?}");
        }
    }

    #[test]
    fn diagnostics_name_each_wrong_entry() {
        let labels = strings(&["harness", "shell"]);
        let orders = BTreeMap::from([
            ("good".to_string(), strings(&["shell", "harness"])),
            ("bad".to_string(), strings(&["shell"])),
        ]);
        let colors = BTreeMap::from([
            ("shell".to_string(), PaneTabColorsConfig::default()),
            ("shel".to_string(), PaneTabColorsConfig::default()),
        ]);
        let diagnostics = pane_tabs_diagnostics(&labels, &orders, &colors);
        assert_eq!(diagnostics.len(), 2, "{diagnostics:?}");
        assert!(diagnostics[0].contains("ui.pane_tab_order.\"bad\""));
        assert!(diagnostics[1].contains("ui.pane_tab_colors.\"shel\""));
    }
}
