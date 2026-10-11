use std::path::PathBuf;

use crate::api::schema::{
    EventData, EventEnvelope, EventKind, ResponseResult, TabCreateParams, TabListParams,
    TabMoveParams, TabMoveToWorkspaceParams, TabRenameParams, TabTarget,
};
use crate::app::{App, Mode};

use super::responses::{encode_error, encode_success};

impl App {
    pub(super) fn handle_tab_list(&mut self, id: String, params: TabListParams) -> String {
        let tabs = if let Some(workspace_id) = params.workspace_id {
            let Some(ws_idx) = self.parse_workspace_id(&workspace_id) else {
                return workspace_not_found(id, &workspace_id);
            };
            let Some(_) = self.state.workspaces.get(ws_idx) else {
                return workspace_not_found(id, &workspace_id);
            };
            self.tab_list_info(ws_idx)
        } else {
            let mut tabs = Vec::new();
            for (ws_idx, ws) in self.state.workspaces.iter().enumerate() {
                for tab_idx in 0..ws.tabs.len() {
                    if let Some(tab) = self.tab_info(ws_idx, tab_idx) {
                        tabs.push(tab);
                    }
                }
            }
            tabs
        };

        encode_success(id, ResponseResult::TabList { tabs })
    }

    pub(super) fn handle_tab_get(&mut self, id: String, target: TabTarget) -> String {
        let Some((ws_idx, tab_idx)) = self.parse_tab_id(&target.tab_id) else {
            return tab_not_found(id, &target.tab_id);
        };
        let Some(tab) = self.tab_info(ws_idx, tab_idx) else {
            return tab_not_found(id, &target.tab_id);
        };

        encode_success(id, ResponseResult::TabInfo { tab })
    }

    pub(super) fn handle_tab_create(&mut self, id: String, params: TabCreateParams) -> String {
        let TabCreateParams {
            workspace_id,
            cwd,
            focus,
            label,
            env,
        } = params;
        let ws_idx = if let Some(workspace_id) = workspace_id {
            let Some(ws_idx) = self.parse_workspace_id(&workspace_id) else {
                return workspace_not_found(id, &workspace_id);
            };
            ws_idx
        } else if let Some(active) = self.state.active {
            active
        } else {
            return encode_error(id, "workspace_not_found", "no active workspace");
        };
        let cwd = cwd.map(PathBuf::from).unwrap_or_else(|| {
            self.resolve_new_terminal_cwd(self.focused_pane_cwd_in_workspace(ws_idx))
        });
        let (rows, cols) = self.state.new_pane_size(crate::ui::NewPanePlacement::Alone);
        let default_shell = self.state.default_shell.clone();
        let scrollback_limit_bytes = self.state.pane_scrollback_limit_bytes;
        let host_terminal_theme = self.state.host_terminal_theme;
        let host_terminal_appearance = self.state.host_terminal_appearance;
        let extra_env = match super::env::normalize_launch_env(env) {
            Ok(env) => env,
            Err((code, message)) => return encode_error(id, &code, message),
        };
        let result = self
            .state
            .workspaces
            .get_mut(ws_idx)
            .ok_or_else(|| std::io::Error::other("workspace disappeared"))
            .and_then(|ws| {
                ws.create_tab(
                    rows,
                    cols,
                    cwd,
                    scrollback_limit_bytes,
                    host_terminal_theme,
                    host_terminal_appearance,
                    crate::pane::PaneShellConfig::new(&default_shell, self.state.shell_mode),
                    extra_env,
                )
            });
        match result {
            Ok((tab_idx, terminal, runtime)) => {
                self.terminal_runtimes.insert(terminal.id.clone(), runtime);
                self.state.terminals.insert(terminal.id.clone(), terminal);
                self.state.remove_alias_shadowed_by_new_pane(
                    self.state.workspaces[ws_idx].tabs[tab_idx].root_pane,
                );
                if let Some(label) = label {
                    let workspace_id = self.state.workspaces[ws_idx].id.clone();
                    let tab_id = self.public_tab_id(ws_idx, tab_idx).unwrap_or_else(|| {
                        crate::workspace::public_tab_id_for_number(&workspace_id, tab_idx + 1)
                    });
                    if let Some(tab) = self
                        .state
                        .workspaces
                        .get_mut(ws_idx)
                        .and_then(|ws| ws.tabs.get_mut(tab_idx))
                    {
                        tab.set_custom_name(label);
                        crate::logging::tab_renamed(&workspace_id, &tab_id);
                    }
                }
                if focus {
                    self.state.switch_workspace_tab(ws_idx, tab_idx);
                    self.state.mode = Mode::Terminal;
                }
                self.schedule_session_save();
                self.emit_tab_created_events(ws_idx, tab_idx);
                encode_success(
                    id,
                    self.tab_created_result(ws_idx, tab_idx)
                        .expect("new tab should produce a complete create response"),
                )
            }
            Err(err) => encode_error(id, "tab_create_failed", err.to_string()),
        }
    }

    pub(super) fn handle_tab_focus(&mut self, id: String, target: TabTarget) -> String {
        let Some((ws_idx, tab_idx)) = self.parse_tab_id(&target.tab_id) else {
            return tab_not_found(id, &target.tab_id);
        };
        self.state.switch_workspace_tab(ws_idx, tab_idx);
        let tab = self.tab_info(ws_idx, tab_idx).unwrap();

        encode_success(id, ResponseResult::TabInfo { tab })
    }

    pub(super) fn handle_tab_rename(&mut self, id: String, params: TabRenameParams) -> String {
        let Some((ws_idx, tab_idx)) = self.parse_tab_id(&params.tab_id) else {
            return tab_not_found(id, &params.tab_id);
        };
        let workspace_id = self.state.workspaces[ws_idx].id.clone();
        let tab_id = self.public_tab_id(ws_idx, tab_idx).unwrap_or_else(|| {
            crate::workspace::public_tab_id_for_number(&workspace_id, tab_idx + 1)
        });
        let Some(tab) = self
            .state
            .workspaces
            .get_mut(ws_idx)
            .and_then(|ws| ws.tabs.get_mut(tab_idx))
        else {
            return tab_not_found(id, &params.tab_id);
        };
        tab.set_custom_name(params.label.clone());
        crate::logging::tab_renamed(&workspace_id, &tab_id);
        self.schedule_session_save();
        self.emit_event(EventEnvelope {
            event: EventKind::TabRenamed,
            data: EventData::TabRenamed {
                tab_id: self.public_tab_id(ws_idx, tab_idx).unwrap(),
                workspace_id: self.public_workspace_id(ws_idx),
                label: params.label,
            },
        });
        let tab = self.tab_info(ws_idx, tab_idx).unwrap();

        encode_success(id, ResponseResult::TabInfo { tab })
    }

    pub(super) fn handle_tab_move(&mut self, id: String, params: TabMoveParams) -> String {
        let Some((ws_idx, tab_idx)) = self.parse_tab_id(&params.tab_id) else {
            return tab_not_found(id, &params.tab_id);
        };
        let Some(ws) = self.state.workspaces.get(ws_idx) else {
            return tab_not_found(id, &params.tab_id);
        };
        if params.insert_index > ws.tabs.len() {
            return encode_error(
                id,
                "tab_move_failed",
                format!("insert_index {} is out of bounds", params.insert_index),
            );
        }

        let tab_id = self
            .public_tab_id(ws_idx, tab_idx)
            .unwrap_or_else(|| crate::workspace::public_tab_id_for_number(&ws.id, tab_idx + 1));
        let workspace_id = self.public_workspace_id(ws_idx);
        let insert_index = params.insert_index;
        let moved = self
            .state
            .workspaces
            .get_mut(ws_idx)
            .is_some_and(|ws| ws.move_tab(tab_idx, insert_index));
        let tabs = self.tab_list_info(ws_idx);
        if moved {
            self.schedule_session_save();
            self.emit_event(EventEnvelope {
                event: EventKind::TabMoved,
                data: EventData::TabMoved {
                    tab_id,
                    workspace_id,
                    insert_index,
                    tabs: tabs.clone(),
                },
            });
        }

        encode_success(id, ResponseResult::TabList { tabs })
    }

    pub(super) fn handle_tab_move_to_workspace(
        &mut self,
        id: String,
        params: TabMoveToWorkspaceParams,
    ) -> String {
        let Some((source_ws_idx, source_tab_idx)) = self.parse_tab_id(&params.tab_id) else {
            return tab_not_found(id, &params.tab_id);
        };
        let Some(previous_tab_id) = self.public_tab_id(source_ws_idx, source_tab_idx) else {
            return tab_not_found(id, &params.tab_id);
        };
        let Some(target_ws_idx) = self.parse_workspace_id(&params.workspace_id) else {
            return workspace_not_found(id, &params.workspace_id);
        };
        if source_ws_idx == target_ws_idx {
            // Already there: left where it is, so a caller that ensures a
            // tab's workspace can ask again without reordering it.
            let Some(tab) = self.tab_info(source_ws_idx, source_tab_idx) else {
                return tab_not_found(id, &params.tab_id);
            };
            return encode_success(id, ResponseResult::TabInfo { tab });
        }
        let source_tabs = self.state.workspaces[source_ws_idx].tabs.len();
        if source_tabs <= 1
            && self
                .state
                .workspace_close_would_close_worktree_group(source_ws_idx)
        {
            return encode_error(
                id,
                "tab_move_failed",
                "moving the last tab out would close a worktree group",
            );
        }
        let previous_workspace_id = self.public_workspace_id(source_ws_idx);
        let target_workspace_id = self.public_workspace_id(target_ws_idx);
        let pane_ids = self.state.workspaces[source_ws_idx].tabs[source_tab_idx]
            .layout
            .pane_ids();
        let previous_pane_ids: Vec<_> = pane_ids
            .iter()
            .filter_map(|&pane| {
                self.public_pane_id(source_ws_idx, pane)
                    .map(|public| (public, pane))
            })
            .collect();

        let previous_focus = self.state.current_pane_focus_target();
        let Some(taken) = self.state.workspaces[source_ws_idx].take_tab_for_move(source_tab_idx)
        else {
            return tab_not_found(id, &params.tab_id);
        };
        // The panes' old public ids keep resolving, as after a pane move;
        // the old tab id does not (no tab aliases exist).
        for (public, pane) in previous_pane_ids {
            self.state.public_pane_id_aliases.insert(public, pane);
        }

        let mut closed_workspace_id = None;
        if taken.workspace_empty {
            let closed = self.state.workspaces.remove(source_ws_idx);
            crate::logging::workspace_closed(&closed.id);
            closed_workspace_id = Some(previous_workspace_id.clone());
            if let Some(active) = self.state.active {
                if active == source_ws_idx {
                    self.state.active = Some(source_ws_idx.min(self.state.workspaces.len() - 1));
                } else if active > source_ws_idx {
                    self.state.active = Some(active - 1);
                }
            }
            if self.state.selected == source_ws_idx {
                self.state.selected = source_ws_idx.min(self.state.workspaces.len() - 1);
            } else if self.state.selected > source_ws_idx {
                self.state.selected -= 1;
            }
        }
        // The source's removal shifts the workspaces after it down by one.
        // Nothing past the take may fail: the tab is out of every workspace.
        let target_ws_idx = if closed_workspace_id.is_some() && target_ws_idx > source_ws_idx {
            target_ws_idx - 1
        } else {
            target_ws_idx
        };
        let tab_idx =
            self.state.workspaces[target_ws_idx].insert_moved_tab(taken.tab, params.insert_index);
        for &pane in &pane_ids {
            self.state.remove_alias_shadowed_by_new_pane(pane);
        }
        self.state
            .retarget_pane_references(&pane_ids, &target_workspace_id);

        if params.focus || self.state.active.is_none() {
            let previous_focus = crate::app::AppState::follow_moved_panes(
                previous_focus,
                &pane_ids,
                &target_workspace_id,
            );
            self.state.switch_workspace_tab(target_ws_idx, tab_idx);
            let focused = self.state.workspaces[target_ws_idx].tabs[tab_idx]
                .layout
                .focused();
            self.state
                .record_pane_focus_change(previous_focus, target_ws_idx, focused);
            self.state.mode = Mode::Terminal;
        }
        self.state.mark_session_dirty();
        self.schedule_session_save();

        let Some(tab) = self.tab_info(target_ws_idx, tab_idx) else {
            return encode_error(id, "tab_move_failed", "the moved tab is unavailable");
        };
        self.emit_event(EventEnvelope {
            event: EventKind::TabClosed,
            data: EventData::TabClosed {
                tab_id: previous_tab_id,
                workspace_id: previous_workspace_id,
            },
        });
        if let Some(workspace_id) = closed_workspace_id {
            self.emit_event(EventEnvelope {
                event: EventKind::WorkspaceClosed,
                data: EventData::WorkspaceClosed {
                    workspace_id,
                    workspace: None,
                },
            });
        }
        self.emit_event(EventEnvelope {
            event: EventKind::TabCreated,
            data: EventData::TabCreated { tab: tab.clone() },
        });

        encode_success(id, ResponseResult::TabInfo { tab })
    }

    pub(super) fn handle_tab_close(&mut self, id: String, target: TabTarget) -> String {
        let Some((ws_idx, tab_idx)) = self.parse_tab_id(&target.tab_id) else {
            return tab_not_found(id, &target.tab_id);
        };
        let Some(tab_id) = self.public_tab_id(ws_idx, tab_idx) else {
            return tab_not_found(id, &target.tab_id);
        };
        let workspace_id = self.public_workspace_id(ws_idx);
        let Some(ws) = self.state.workspaces.get(ws_idx) else {
            return tab_not_found(id, &target.tab_id);
        };
        let closes_workspace = ws.tabs.len() <= 1;
        let terminal_ids = self.state.terminal_ids_for_tab(ws_idx, tab_idx);
        let pane_ids = ws
            .tabs
            .get(tab_idx)
            .map(|tab| tab.layout.pane_ids())
            .unwrap_or_default();

        if closes_workspace {
            if let Err(response) = self.require_restored_group_close_ready(
                &id,
                &self.state.workspace_close_indices(ws_idx),
            ) {
                return response;
            }
            if self.state.confirm_implicit_worktree_group_close(ws_idx) {
                return encode_error(
                    id,
                    "confirmation_required",
                    "closing this tab would close a worktree group",
                );
            }
            let workspace = self.workspace_info(ws_idx);
            self.state.selected = ws_idx;
            self.state.close_selected_workspace();
            self.state.remove_plugin_pane_records(pane_ids);
            self.shutdown_detached_terminal_runtimes();
            self.emit_event(EventEnvelope {
                event: EventKind::TabClosed,
                data: EventData::TabClosed {
                    tab_id,
                    workspace_id: workspace_id.clone(),
                },
            });
            self.emit_event(EventEnvelope {
                event: EventKind::WorkspaceClosed,
                data: EventData::WorkspaceClosed {
                    workspace_id,
                    workspace: Some(workspace),
                },
            });
            return encode_success(id, ResponseResult::Ok {});
        }

        let Some(ws) = self.state.workspaces.get_mut(ws_idx) else {
            return tab_not_found(id, &target.tab_id);
        };
        if !ws.close_tab(tab_idx) {
            return encode_error(
                id,
                "tab_close_failed",
                format!("tab {} could not be closed", target.tab_id),
            );
        }
        self.state.remove_plugin_pane_records(pane_ids);
        self.state.remove_unattached_terminal_ids(terminal_ids);
        self.shutdown_detached_terminal_runtimes();
        self.schedule_session_save();
        self.emit_event(EventEnvelope {
            event: EventKind::TabClosed,
            data: EventData::TabClosed {
                tab_id,
                workspace_id,
            },
        });

        encode_success(id, ResponseResult::Ok {})
    }

    fn tab_list_info(&self, ws_idx: usize) -> Vec<crate::api::schema::TabInfo> {
        self.state
            .workspaces
            .get(ws_idx)
            .map(|ws| {
                (0..ws.tabs.len())
                    .filter_map(|idx| self.tab_info(ws_idx, idx))
                    .collect()
            })
            .unwrap_or_default()
    }
}

fn workspace_not_found(id: String, workspace_id: &str) -> String {
    encode_error(
        id,
        "workspace_not_found",
        format!("workspace {workspace_id} not found"),
    )
}

fn tab_not_found(id: String, tab_id: &str) -> String {
    encode_error(id, "tab_not_found", format!("tab {tab_id} not found"))
}

#[cfg(test)]
mod tests {
    use super::super::test_support::{exiting_test_command, shutdown_test_runtimes};
    use super::*;
    use crate::{
        api::schema::SuccessResponse,
        config::{Config, ShellModeConfig},
        workspace::Workspace,
    };

    #[test]
    fn api_tab_close_last_tab_closes_workspace_and_emits_both_events() {
        let event_hub = crate::api::EventHub::default();
        let (_api_tx, api_rx) = tokio::sync::mpsc::unbounded_channel();
        let mut app = App::new(
            &Config::default(),
            crate::app::AppPolicy::TEST,
            None,
            api_rx,
            event_hub.clone(),
        );
        app.state.workspaces = vec![Workspace::test_new("tabs")];
        app.state.active = Some(0);
        app.state.selected = 0;
        let tab_id = app.public_tab_id(0, 0).unwrap();
        let workspace_id = app.public_workspace_id(0);

        let response = app.handle_tab_close(
            "req".into(),
            TabTarget {
                tab_id: tab_id.clone(),
            },
        );

        let success: SuccessResponse = serde_json::from_str(&response).unwrap();
        assert_eq!(success.result, ResponseResult::Ok {});
        assert!(app.state.workspaces.is_empty());
        assert!(app.state.active.is_none());
        let events = event_hub.events_after(0);
        assert_eq!(
            events
                .iter()
                .map(|(_, event)| event.event)
                .collect::<Vec<_>>(),
            [EventKind::TabClosed, EventKind::WorkspaceClosed]
        );
        assert!(matches!(
            &events[0].1.data,
            EventData::TabClosed {
                tab_id: closed_tab_id,
                workspace_id: closed_workspace_id,
            } if closed_tab_id == &tab_id && closed_workspace_id == &workspace_id
        ));
        assert!(matches!(
            &events[1].1.data,
            EventData::WorkspaceClosed {
                workspace_id: closed_workspace_id,
                workspace: Some(workspace),
            } if closed_workspace_id == &workspace_id
                && workspace.workspace_id == workspace_id
        ));
    }

    fn move_app() -> (App, crate::api::EventHub) {
        let event_hub = crate::api::EventHub::default();
        let (_api_tx, api_rx) = tokio::sync::mpsc::unbounded_channel();
        let app = App::new(
            &Config::default(),
            crate::app::AppPolicy::TEST,
            None,
            api_rx,
            event_hub.clone(),
        );
        (app, event_hub)
    }

    fn move_to_workspace(
        app: &mut App,
        tab_id: &str,
        workspace_id: &str,
        insert_index: Option<usize>,
        focus: bool,
    ) -> String {
        app.handle_tab_move_to_workspace(
            "req".into(),
            TabMoveToWorkspaceParams {
                tab_id: tab_id.into(),
                workspace_id: workspace_id.into(),
                insert_index,
                focus,
            },
        )
    }

    fn event_kinds(event_hub: &crate::api::EventHub) -> Vec<EventKind> {
        event_hub
            .events_after(0)
            .iter()
            .map(|(_, event)| event.event)
            .collect()
    }

    #[test]
    fn api_tab_move_to_workspace_carries_live_panes_and_renumbers_them() {
        let (mut app, event_hub) = move_app();
        let mut target = Workspace::test_new("target");
        target.test_add_tab(Some("second"));
        app.state = crate::app::AppState::test_with_adversarial_identity_state();
        app.state.workspaces.push(target);
        app.state.ensure_test_terminals();
        let source_id = app.public_workspace_id(0);
        let target_id = app.public_workspace_id(1);
        // The tab with the most panes, at a position that is not its number.
        let tab_idx = (0..app.state.workspaces[0].tabs.len())
            .max_by_key(|&idx| app.state.workspaces[0].tabs[idx].layout.pane_count())
            .unwrap();
        let moved_tab_id = app.public_tab_id(0, tab_idx).unwrap();
        let panes = app.state.workspaces[0].tabs[tab_idx].layout.pane_ids();
        assert!(panes.len() > 1, "the moved tab must hold several panes");
        let old_public: Vec<_> = panes
            .iter()
            .map(|&pane| (app.public_pane_id(0, pane).unwrap(), pane))
            .collect();
        let terminals: Vec<_> = panes
            .iter()
            .map(|pane| {
                app.state.workspaces[0].tabs[tab_idx]
                    .terminal_id(*pane)
                    .cloned()
            })
            .collect();
        app.state.previous_pane_focus = Some(crate::app::state::PaneFocusTarget {
            workspace_id: source_id.clone(),
            pane_id: panes[0],
        });
        let source_tabs = app.state.workspaces[0].tabs.len();

        let response = move_to_workspace(&mut app, &moved_tab_id, &target_id, Some(0), false);

        let success: SuccessResponse = serde_json::from_str(&response).unwrap();
        let ResponseResult::TabInfo { tab } = success.result else {
            panic!("expected the moved tab: {response}");
        };
        app.state.assert_invariants_for_test();
        assert_eq!(app.state.workspaces[0].tabs.len(), source_tabs - 1);
        assert_eq!(app.state.workspaces[1].tabs.len(), 3);
        assert_eq!(app.state.workspaces[1].tabs[0].layout.pane_ids(), panes);
        assert_eq!(tab.workspace_id, target_id);
        assert_eq!(tab.tab_id, app.public_tab_id(1, 0).unwrap());
        let moved_terminals: Vec<_> = panes
            .iter()
            .map(|pane| app.state.workspaces[1].tabs[0].terminal_id(*pane).cloned())
            .collect();
        assert_eq!(moved_terminals, terminals, "the panes keep their terminals");
        for (public, pane) in &old_public {
            assert_eq!(
                app.parse_pane_id(public),
                Some((1, *pane)),
                "{public} still resolves"
            );
        }
        assert!(
            app.parse_tab_id(&moved_tab_id).is_none(),
            "no tab aliases exist"
        );
        assert_eq!(
            app.state
                .previous_pane_focus
                .as_ref()
                .map(|f| f.workspace_id.clone()),
            Some(target_id.clone())
        );
        assert_eq!(
            app.state.active,
            Some(0),
            "no focus asked: the active workspace stays"
        );
        assert_eq!(
            event_kinds(&event_hub),
            [EventKind::TabClosed, EventKind::TabCreated]
        );
    }

    #[test]
    fn api_tab_move_to_workspace_closes_an_emptied_source_before_the_target() {
        let (mut app, event_hub) = move_app();
        app.state.workspaces = vec![Workspace::test_new("only"), Workspace::test_new("target")];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        app.state.selected = 0;
        let tab_id = app.public_tab_id(0, 0).unwrap();
        let root = app.state.workspaces[0].tabs[0].root_pane;
        let target_id = app.public_workspace_id(1);

        let response = move_to_workspace(&mut app, &tab_id, &target_id, None, false);

        assert!(
            serde_json::from_str::<SuccessResponse>(&response).is_ok(),
            "{response}"
        );
        app.state.assert_invariants_for_test();
        assert_eq!(app.state.workspaces.len(), 1);
        assert_eq!(app.public_workspace_id(0), target_id);
        assert_eq!(
            app.state.workspaces[0].tabs[1].root_pane, root,
            "at the end"
        );
        assert_eq!((app.state.active, app.state.selected), (Some(0), 0));
        assert_eq!(
            event_kinds(&event_hub),
            [
                EventKind::TabClosed,
                EventKind::WorkspaceClosed,
                EventKind::TabCreated
            ]
        );
    }

    #[test]
    fn api_tab_move_to_its_own_workspace_changes_nothing() {
        let (mut app, event_hub) = move_app();
        let mut workspace = Workspace::test_new("tabs");
        workspace.test_add_tab(Some("two"));
        app.state.workspaces = vec![workspace];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        let tab_id = app.public_tab_id(0, 0).unwrap();
        let workspace_id = app.public_workspace_id(0);

        let response = move_to_workspace(&mut app, &tab_id, &workspace_id, Some(2), true);

        let success: SuccessResponse = serde_json::from_str(&response).unwrap();
        assert!(matches!(success.result, ResponseResult::TabInfo { tab } if tab.tab_id == tab_id));
        assert_eq!(app.public_tab_id(0, 0).as_deref(), Some(tab_id.as_str()));
        assert!(event_kinds(&event_hub).is_empty());
    }

    #[test]
    fn api_tab_move_to_workspace_focuses_the_moved_tab_when_asked() {
        let (mut app, _event_hub) = move_app();
        let mut source = Workspace::test_new("source");
        source.test_add_tab(Some("moved"));
        app.state.workspaces = vec![source, Workspace::test_new("target")];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        let tab_id = app.public_tab_id(0, 1).unwrap();
        let target_id = app.public_workspace_id(1);

        move_to_workspace(&mut app, &tab_id, &target_id, None, true);

        app.state.assert_invariants_for_test();
        assert_eq!(app.state.active, Some(1));
        assert_eq!(app.state.workspaces[1].active_tab, 1);
    }

    #[test]
    fn api_tab_move_to_workspace_of_the_focused_tab_with_focus_keeps_the_focus_record_valid() {
        let (mut app, _event_hub) = move_app();
        let mut source = Workspace::test_new("source");
        source.test_split(ratatui::layout::Direction::Horizontal);
        app.state.workspaces = vec![source, Workspace::test_new("target")];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        let tab_id = app.public_tab_id(0, 0).unwrap();
        let target_id = app.public_workspace_id(1);
        let focused = app.state.workspaces[0].tabs[0].layout.focused();

        move_to_workspace(&mut app, &tab_id, &target_id, None, true);

        // The emptied source is gone: a focus record still naming it would
        // name a missing workspace.
        app.state.assert_invariants_for_test();
        assert_eq!(app.state.active, Some(0));
        assert_eq!(app.public_workspace_id(0), target_id);
        if let Some(previous) = &app.state.previous_pane_focus {
            assert_ne!(
                (previous.workspace_id.as_str(), previous.pane_id),
                (target_id.as_str(), focused),
                "the moved pane stays focused: it is not its own previous focus"
            );
        }
    }

    #[test]
    fn api_tab_move_to_workspace_points_toasts_and_notifications_at_the_target() {
        let (mut app, _event_hub) = move_app();
        let mut source = Workspace::test_new("source");
        source.test_add_tab(Some("moved"));
        app.state.workspaces = vec![source, Workspace::test_new("target")];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        let source_id = app.public_workspace_id(0);
        let target_id = app.public_workspace_id(1);
        let pane = app.state.workspaces[0].tabs[1].root_pane;
        let tab_id = app.public_tab_id(0, 1).unwrap();
        app.state.toast = Some(crate::app::state::ToastNotification {
            kind: crate::app::ToastKind::NeedsAttention,
            title: "t".into(),
            context: "c".into(),
            position: None,
            target: Some(crate::app::state::ToastTarget {
                workspace_id: source_id.clone(),
                pane_id: pane,
            }),
        });
        app.state.pending_agent_notifications.insert(
            pane,
            crate::app::state::PendingAgentNotification {
                pane_id: pane,
                workspace_id: source_id,
                agent_label: "claude".into(),
                known_agent: None,
                kind: crate::app::ToastKind::NeedsAttention,
                state: crate::detect::AgentState::Idle,
                deadline: std::time::Instant::now(),
            },
        );

        move_to_workspace(&mut app, &tab_id, &target_id, None, false);

        app.state.assert_invariants_for_test();
        let toast_target = app
            .state
            .toast
            .as_ref()
            .and_then(|toast| toast.target.as_ref());
        assert_eq!(
            toast_target.map(|t| t.workspace_id.as_str()),
            Some(target_id.as_str())
        );
        assert_eq!(
            app.state.pending_agent_notifications[&pane].workspace_id,
            target_id
        );
    }

    #[test]
    fn api_tab_move_of_a_worktree_parents_last_tab_is_refused_and_moves_nothing() {
        let (mut app, event_hub) = move_app();
        let membership = |linked: bool| crate::workspace::WorktreeSpaceMembership {
            key: "repo-key".into(),
            label: "herdr".into(),
            repo_root: "/repo/herdr".into(),
            checkout_path: if linked { "/repo/wt" } else { "/repo/herdr" }.into(),
            is_linked_worktree: linked,
        };
        let mut parent = Workspace::test_new("parent");
        parent.worktree_space = Some(membership(false));
        let mut linked = Workspace::test_new("linked");
        linked.worktree_space = Some(membership(true));
        app.state.workspaces = vec![parent, linked, Workspace::test_new("elsewhere")];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        let tab_id = app.public_tab_id(0, 0).unwrap();
        let target_id = app.public_workspace_id(2);

        let response = move_to_workspace(&mut app, &tab_id, &target_id, None, false);

        let error: crate::api::schema::ErrorResponse = serde_json::from_str(&response).unwrap();
        assert_eq!(error.error.code, "tab_move_failed");
        assert_eq!(app.state.workspaces.len(), 3);
        assert_eq!(app.public_tab_id(0, 0).as_deref(), Some(tab_id.as_str()));
        assert!(event_kinds(&event_hub).is_empty());
        app.state.assert_invariants_for_test();
    }

    #[test]
    fn api_tab_move_of_an_unknown_tab_is_refused() {
        let (mut app, event_hub) = move_app();
        app.state.workspaces = vec![Workspace::test_new("only"), Workspace::test_new("target")];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        let target_id = app.public_workspace_id(1);

        let response = move_to_workspace(&mut app, "w_missing:t9", &target_id, None, false);

        let error: crate::api::schema::ErrorResponse = serde_json::from_str(&response).unwrap();
        assert_eq!(error.error.code, "tab_not_found");
        assert!(event_kinds(&event_hub).is_empty());
    }

    #[test]
    fn api_tab_move_to_an_unknown_workspace_is_refused_and_moves_nothing() {
        let (mut app, event_hub) = move_app();
        app.state.workspaces = vec![Workspace::test_new("only")];
        app.state.ensure_test_terminals();
        app.state.active = Some(0);
        let tab_id = app.public_tab_id(0, 0).unwrap();

        let response = move_to_workspace(&mut app, &tab_id, "w_missing", None, false);

        let error: crate::api::schema::ErrorResponse = serde_json::from_str(&response).unwrap();
        assert_eq!(error.error.code, "workspace_not_found");
        assert_eq!(app.state.workspaces[0].tabs.len(), 1);
        assert!(event_kinds(&event_hub).is_empty());
    }

    #[test]
    fn api_tab_move_reorders_tabs_in_target_workspace() {
        let event_hub = crate::api::EventHub::default();
        let (_api_tx, api_rx) = tokio::sync::mpsc::unbounded_channel();
        let mut app = App::new(
            &Config::default(),
            crate::app::AppPolicy::TEST,
            None,
            api_rx,
            event_hub.clone(),
        );
        let mut workspace = Workspace::test_new("tabs");
        workspace.test_add_tab(Some("two"));
        workspace.test_add_tab(Some("three"));
        app.state.workspaces = vec![workspace];
        app.state.active = Some(0);
        app.state.selected = 0;
        let moved_root = app.state.workspaces[0].tabs[0].root_pane;
        let moved_id = app.public_tab_id(0, 0).unwrap();

        let response = app.handle_tab_move(
            "req".into(),
            TabMoveParams {
                tab_id: moved_id.clone(),
                insert_index: 3,
            },
        );

        let success: SuccessResponse = serde_json::from_str(&response).unwrap();
        let ResponseResult::TabList { tabs } = success.result else {
            panic!("expected tab list");
        };
        assert_eq!(app.state.workspaces[0].tabs[2].root_pane, moved_root);
        assert_eq!(tabs[2].tab_id, app.public_tab_id(0, 2).unwrap());
        let events = event_hub.events_after(0);
        assert!(events.iter().any(|(_, event)| {
            matches!(
                &event.data,
                EventData::TabMoved {
                    tab_id,
                    workspace_id,
                    insert_index: 3,
                    tabs,
                } if tab_id == &moved_id
                    && workspace_id == &app.public_workspace_id(0)
                    && tabs[2].tab_id == moved_id
            )
        }));
    }

    #[tokio::test]
    async fn tab_create_follows_cached_focused_pane_cwd_without_runtime() {
        let event_hub = crate::api::EventHub::default();
        let (_api_tx, api_rx) = tokio::sync::mpsc::unbounded_channel();
        let mut app = App::new(
            &Config::default(),
            crate::app::AppPolicy::TEST,
            None,
            api_rx,
            event_hub,
        );
        app.state.default_shell = exiting_test_command().into();
        app.state.shell_mode = ShellModeConfig::NonLogin;
        let workspace = Workspace::test_new("tabs");
        let focused_pane = workspace.tabs[0].root_pane;
        app.state.workspaces = vec![workspace];
        app.state.active = Some(0);
        app.state.selected = 0;
        app.state.ensure_test_terminals();
        let cached_cwd = std::env::temp_dir();
        let terminal_id = app.state.workspaces[0]
            .terminal_id(focused_pane)
            .cloned()
            .unwrap();
        app.state.terminals.get_mut(&terminal_id).unwrap().cwd = cached_cwd.clone();

        let response = app.handle_tab_create(
            "req".into(),
            TabCreateParams {
                workspace_id: None,
                cwd: None,
                focus: false,
                label: None,
                env: Default::default(),
            },
        );

        let success: SuccessResponse = serde_json::from_str(&response).unwrap();
        assert!(matches!(success.result, ResponseResult::TabCreated { .. }));
        let created = &app.state.workspaces[0].tabs[1];
        let created_terminal_id = created.terminal_id(created.root_pane).unwrap();
        let created_cwd = &app.state.terminals.get(created_terminal_id).unwrap().cwd;
        assert_eq!(
            crate::worktree::canonical_or_original(created_cwd),
            crate::worktree::canonical_or_original(&cached_cwd)
        );
        shutdown_test_runtimes(&mut app);
    }
}
