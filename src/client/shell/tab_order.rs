//! `ui.tab_order`: the tab labels in the order each workspace keeps its tabs.
//!
//! The order is the server's, not drawn over it: tab numbers, the keys that
//! go to tab N, a drag and every other attached client all read the server's
//! order, so a client that only drew its own would show positions its keys
//! do not mean. This client moves the server's tabs instead, one `tab.move`
//! per snapshot, until the snapshot it sees is in order.

use super::*;

use crate::api::schema::{Method, TabMoveParams};

/// The one move that brings a workspace's tabs nearer `order`: listed tabs
/// first, in the listed order (tabs sharing a label keep theirs), then the
/// rest as they are. `None` when every workspace is in order.
pub(super) fn next_tab_order_move(
    snapshot: &ClientShellSnapshot,
    order: &[String],
) -> Option<TabMoveParams> {
    if order.is_empty() {
        return None;
    }
    let rank = |tab: &ClientShellTab| {
        order
            .iter()
            .position(|label| *label == tab.label)
            .unwrap_or(order.len())
    };
    for workspace in &snapshot.workspaces {
        let mut tabs: Vec<&ClientShellTab> = snapshot
            .tabs
            .iter()
            .filter(|tab| tab.workspace_id == workspace.workspace_id)
            .collect();
        tabs.sort_by_key(|tab| tab.number);
        let mut wanted = tabs.clone();
        // A stable sort: equal ranks, unlisted tabs included, keep their order.
        wanted.sort_by_key(|tab| rank(tab));
        let Some(index) = (0..tabs.len()).find(|&index| tabs[index].tab_id != wanted[index].tab_id)
        else {
            continue;
        };
        // The wanted tab sits later than `index` (everything before it is in
        // place), so the slot before `index` is where it lands.
        return Some(TabMoveParams {
            tab_id: wanted[index].tab_id.clone(),
            insert_index: index,
        });
    }
    None
}

impl ClientShellState {
    /// The `tab.move` this snapshot needs, if any, as input to send. A move is
    /// asked once per tab arrangement: a server that refuses it, or that
    /// another client keeps rearranging, is not asked again until the tabs
    /// change.
    pub(crate) fn tab_order_outcome(&mut self) -> Option<ClientShellInput> {
        let snapshot = self.snapshot.as_deref()?;
        let Some(params) = next_tab_order_move(snapshot, &self.config.tab_order) else {
            self.tab_order_asked = None;
            return None;
        };
        let arrangement: Vec<String> = snapshot.tabs.iter().map(|tab| tab.tab_id.clone()).collect();
        let method = Method::TabMove(params);
        if self.tab_order_asked.as_ref() == Some(&arrangement)
            || !self.endpoint_is_online(&self.active_endpoint_id)
            || !self.supports_endpoint_method(&method)
        {
            return None;
        }
        self.tab_order_asked = Some(arrangement);
        let mut outcome = ClientShellInput::default();
        self.push_endpoint_method(method, &mut outcome);
        Some(outcome)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot(workspaces: &[(&str, &[&str])]) -> ClientShellSnapshot {
        let mut snapshot = crate::client::shell::tests::snapshot();
        let template_workspace = snapshot.workspaces[0].clone();
        let template_tab = snapshot.tabs[0].clone();
        snapshot.workspaces = workspaces
            .iter()
            .map(|(id, _)| ClientShellWorkspace {
                workspace_id: (*id).into(),
                ..template_workspace.clone()
            })
            .collect();
        snapshot.tabs = workspaces
            .iter()
            .flat_map(|(workspace, labels)| {
                let template_tab = template_tab.clone();
                labels
                    .iter()
                    .enumerate()
                    .map(move |(index, label)| ClientShellTab {
                        tab_id: format!("{workspace}-{label}"),
                        workspace_id: (*workspace).into(),
                        number: index + 1,
                        label: (*label).into(),
                        ..template_tab.clone()
                    })
            })
            .collect();
        snapshot
    }

    fn order(labels: &[&str]) -> Vec<String> {
        labels.iter().map(|label| label.to_string()).collect()
    }

    /// Applies moves as the server does (`Workspace::move_tab`) until none is
    /// asked, and returns each workspace's labels.
    fn settle(mut snapshot: ClientShellSnapshot, order: &[String]) -> (Vec<String>, usize) {
        let mut moves = 0;
        while let Some(params) = next_tab_order_move(&snapshot, order) {
            moves += 1;
            assert!(moves < 20, "the moves converge");
            let tab = snapshot
                .tabs
                .iter()
                .find(|tab| tab.tab_id == params.tab_id)
                .expect("a move names a tab")
                .clone();
            let mut tabs: Vec<_> = snapshot
                .tabs
                .iter()
                .filter(|other| other.workspace_id == tab.workspace_id)
                .cloned()
                .collect();
            tabs.sort_by_key(|tab| tab.number);
            let source = tabs
                .iter()
                .position(|other| other.tab_id == tab.tab_id)
                .unwrap();
            let target = if source < params.insert_index {
                params.insert_index - 1
            } else {
                params.insert_index
            };
            let moved = tabs.remove(source);
            tabs.insert(target, moved);
            for (index, moved) in tabs.iter().enumerate() {
                let tab = snapshot
                    .tabs
                    .iter_mut()
                    .find(|tab| tab.tab_id == moved.tab_id)
                    .unwrap();
                tab.number = index + 1;
            }
        }
        let mut tabs = snapshot.tabs.clone();
        tabs.sort_by_key(|tab| (tab.workspace_id.clone(), tab.number));
        (tabs.into_iter().map(|tab| tab.label).collect(), moves)
    }

    #[test]
    fn listed_tabs_come_first_in_the_listed_order_and_the_rest_keep_theirs() {
        let snapshot = snapshot(&[("w1", &["notes", "b", "scratch", "a", "fleet"])]);
        let (labels, moves) = settle(snapshot, &order(&["fleet", "a", "b"]));
        assert_eq!(labels, ["fleet", "a", "b", "notes", "scratch"]);
        assert_eq!(moves, 3);
    }

    #[test]
    fn each_workspace_is_ordered_and_one_in_order_asks_nothing() {
        let snapshot = snapshot(&[("w1", &["fleet", "a"]), ("w2", &["b", "a"])]);
        let (labels, moves) = settle(snapshot, &order(&["fleet", "a", "b"]));
        assert_eq!(labels, ["fleet", "a", "a", "b"]);
        assert_eq!(moves, 1);

        let in_order = self::snapshot(&[("w1", &["a", "x", "y"])]);
        assert_eq!(next_tab_order_move(&in_order, &order(&["a", "b"])), None);
        assert_eq!(
            next_tab_order_move(&in_order, &[]),
            None,
            "no order, no move"
        );
    }

    #[test]
    fn a_move_is_asked_once_per_arrangement() {
        let mut config = ClientShellConfig::from_config(&crate::config::Config::default());
        config.tab_order = order(&["a", "b"]);
        let mut state = ClientShellState::new(config);
        state.set_snapshot(Box::new(snapshot(&[("w1", &["b", "a"])])));
        let first = state.tab_order_outcome().expect("out of order: one move");
        assert!(matches!(
            first.actions.as_slice(),
            [ClientShellAction::Endpoint { request, .. }]
                if request.method == Method::TabMove(TabMoveParams {
                    tab_id: "w1-a".into(),
                    insert_index: 0,
                })
        ));
        assert!(
            state.tab_order_outcome().is_none(),
            "the same arrangement again (the move refused, or not yet applied) asks nothing"
        );
        state.set_snapshot(Box::new(snapshot(&[("w1", &["b", "c", "a"])])));
        assert!(
            state.tab_order_outcome().is_some(),
            "a new arrangement is looked at afresh"
        );
    }
}
