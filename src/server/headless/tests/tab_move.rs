use super::*;
use crate::api::schema::{ResponseResult, SuccessResponse, TabMoveToWorkspaceParams};

fn tab_move_server() -> HeadlessServer {
    let mut server = test_headless_server();
    let mut first = crate::workspace::Workspace::test_new("first");
    first.test_add_tab(Some("moved"));
    first.switch_tab(1);
    server.app.state.workspaces = vec![first, crate::workspace::Workspace::test_new("second")];
    server.app.state.ensure_test_terminals();
    server.app.state.active = Some(0);
    server.app.state.selected = 0;
    server.app.state.mode = crate::app::Mode::Terminal;
    server
}

fn public_tab_move(server: &mut HeadlessServer, params: TabMoveToWorkspaceParams) -> String {
    let (respond_to, response_rx) = std::sync::mpsc::channel();
    server.handle_api_request_with_shutdown_check(crate::api::ApiRequestMessage {
        request: crate::api::schema::Request {
            id: "move-tab".into(),
            method: crate::api::schema::Method::TabMoveToWorkspace(params),
        },
        respond_to,
        response_write_complete: None,
    });
    let response = response_rx.recv().expect("tab move response");
    match serde_json::from_str::<SuccessResponse>(&response) {
        Ok(SuccessResponse {
            result: ResponseResult::TabInfo { tab },
            ..
        }) => tab.tab_id,
        other => panic!("expected the moved tab, got {other:?}: {response}"),
    }
}

#[tokio::test]
async fn public_tab_move_with_focus_moves_the_attached_client_with_the_tab() {
    let mut server = tab_move_server();
    let moved = server.app.public_tab_id(0, 1).unwrap();
    let destination = server.app.public_workspace_id(1);
    let (control_rx, _render_rx) = connect_test_shell(&mut server, 9, 80, 23);
    let initial = client_shell_snapshot(&control_rx);

    let new_tab_id = public_tab_move(
        &mut server,
        TabMoveToWorkspaceParams {
            tab_id: moved,
            workspace_id: destination.clone(),
            insert_index: None,
            focus: true,
        },
    );

    assert_eq!(server.app.state.active, Some(1));
    let location = server.clients[&9].shell_location.as_ref().unwrap();
    assert_eq!(
        location.focused_workspace_id.as_deref(),
        Some(destination.as_str()),
        "a public tab move with focus must move the attached client"
    );
    assert_eq!(location.focused_tab_id(), Some(new_tab_id.as_str()));
    server.render_and_stream();
    let snapshot = client_shell_snapshot(&control_rx);
    assert!(snapshot.revision > initial.revision);
    assert_eq!(
        snapshot.focused_tab_id.as_deref(),
        Some(new_tab_id.as_str())
    );
    server.app.state.assert_invariants_for_test();
    shutdown_test_runtimes(&mut server);
}

#[tokio::test]
async fn public_tab_move_with_focus_into_the_active_position_still_moves_the_client() {
    // The server is on the target's first tab, and the moved tab is put
    // there: the active workspace and tab index are the same before and after.
    let mut server = tab_move_server();
    server.app.state.active = Some(1);
    server.app.state.selected = 1;
    let moved = server.app.public_tab_id(0, 1).unwrap();
    let destination = server.app.public_workspace_id(1);
    let (_control, _render) = connect_test_shell(&mut server, 9, 80, 23);

    let new_tab_id = public_tab_move(
        &mut server,
        TabMoveToWorkspaceParams {
            tab_id: moved,
            workspace_id: destination,
            insert_index: Some(0),
            focus: true,
        },
    );

    let location = server.clients[&9].shell_location.as_ref().unwrap();
    assert_eq!(location.focused_tab_id(), Some(new_tab_id.as_str()));
    server.app.state.assert_invariants_for_test();
    shutdown_test_runtimes(&mut server);
}

#[tokio::test]
async fn public_tab_move_to_its_own_workspace_with_focus_leaves_clients_where_they_are() {
    let mut server = tab_move_server();
    let tab = server.app.public_tab_id(0, 1).unwrap();
    let staying = server.app.public_tab_id(0, 0).unwrap();
    let own = server.app.public_workspace_id(0);
    let (_control, _render) = connect_test_shell(&mut server, 9, 80, 23);
    assert!(server.focus_shell_client_on_tab(9, &staying));
    let location_before = server.clients[&9].shell_location.clone();

    public_tab_move(
        &mut server,
        TabMoveToWorkspaceParams {
            tab_id: tab,
            workspace_id: own,
            insert_index: None,
            focus: true,
        },
    );

    assert_eq!(server.clients[&9].shell_location, location_before);
    shutdown_test_runtimes(&mut server);
}

#[tokio::test]
async fn public_tab_move_without_focus_leaves_a_client_on_another_tab_where_it_is() {
    let mut server = tab_move_server();
    let moved = server.app.public_tab_id(0, 1).unwrap();
    let staying = server.app.public_tab_id(0, 0).unwrap();
    let destination = server.app.public_workspace_id(1);
    let (_control, _render) = connect_test_shell(&mut server, 9, 80, 23);
    assert!(server.focus_shell_client_on_tab(9, &staying));
    let location_before = server.clients[&9].shell_location.clone();

    public_tab_move(
        &mut server,
        TabMoveToWorkspaceParams {
            tab_id: moved,
            workspace_id: destination,
            insert_index: None,
            focus: false,
        },
    );

    assert_eq!(server.clients[&9].shell_location, location_before);
    server.app.state.assert_invariants_for_test();
    shutdown_test_runtimes(&mut server);
}
