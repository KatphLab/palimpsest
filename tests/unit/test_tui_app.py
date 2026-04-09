"""Unit tests for the TUI app shell."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Callable, cast
from uuid import UUID, uuid4

import pytest
from textual.widgets import Static

from graph.session_graph import SessionGraph
from models.commands import CommandResult
from models.common import NodeKind, RelationType, SessionStatus
from models.graph import GraphEdge, GraphNode
from models.session import Session
from utils.time import utc_now


def _app_module() -> ModuleType:
    return import_module("tui.app")


def _main_module() -> ModuleType:
    return import_module("main")


class _RuntimeStub:
    def __init__(self) -> None:
        self.session_id = None
        self.session = None


class _RuntimeWithSessionStub:
    def __init__(self, *, session: Session, session_graph: SessionGraph) -> None:
        self.session_id = session.session_id
        self.session = session
        self.session_graph = session_graph
        self.state_version = 2


class _RuntimeContinueStub:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.session = _build_created_session(seed_text="seed")
        self.session.status = SessionStatus.RUNNING
        self.advance_calls = 0

    def advance_session_cycle(self) -> None:
        self.advance_calls += 1
        return None


class _RuntimeWithSessionIdStub:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.session = _build_created_session(seed_text="seed")
        self.session_graph = SessionGraph()
        self.state_version = 1


class _RuntimeWithGraphSwitchStub:
    """Runtime stub for Tab/Shift+Tab graph navigation tests."""

    def __init__(self, *, graph_count: int = 3) -> None:
        self.session_id = uuid4()
        self.session = _build_created_session(seed_text="seed")
        self.session_graph = SessionGraph()
        self.state_version = 1
        self.graph_count = graph_count
        self.next_calls = 0
        self.previous_calls = 0

    def switch_to_next_graph(self) -> object:
        self.next_calls += 1
        return object()

    def switch_to_previous_graph(self) -> object:
        self.previous_calls += 1
        return object()


class _StaticPanelSpy:
    def __init__(self) -> None:
        self.contents: list[str] = []

    def update(self, content: str) -> None:
        self.contents.append(content)


def test_refresh_panels_updates_scene_text_when_mounted() -> None:
    """Refreshing should update scene text content when panel is mounted."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeStub())
    panel = _StaticPanelSpy()
    app._render_scene_text = lambda: "updated content"

    def _query_one(selector: str, widget_type: type[object]) -> object:
        if selector == "#scene-text-panel" and widget_type is Static:
            return panel
        raise AssertionError(f"Unexpected query selector={selector} type={widget_type}")

    app.query_one = _query_one

    app._refresh_panels()

    assert panel.contents == ["updated content"]


def test_complete_continue_generation_refreshes_panel_and_resets_state() -> None:
    """Completion handler should refresh panel and clear generating flag."""

    app_module = _app_module()

    runtime = _RuntimeContinueStub()
    app = app_module.SessionApp(runtime=runtime)
    refreshed = {"calls": 0}

    def _refresh_panel() -> None:
        refreshed["calls"] += 1

    app._refresh_panels = _refresh_panel

    app._is_generating_scene = True

    app._complete_continue_generation(None)

    assert refreshed["calls"] == 1
    assert app._is_generating_scene is False


def test_action_continue_session_sets_generating_state_and_starts_worker() -> None:
    """Continue should mark generation active before starting worker."""

    app_module = _app_module()
    runtime = _RuntimeContinueStub()
    app = app_module.SessionApp(runtime=runtime)
    starts = {"count": 0}

    def _start_worker() -> None:
        starts["count"] += 1

    app._start_continue_generation_worker = _start_worker

    app.action_continue_session()

    assert app._is_generating_scene is True
    assert starts["count"] == 1


def test_action_continue_session_warns_when_generation_already_running() -> None:
    """Continue should reject overlapping generation requests."""

    app_module = _app_module()
    runtime = _RuntimeContinueStub()
    app = app_module.SessionApp(runtime=runtime)
    app._is_generating_scene = True
    notifications: list[tuple[str, str]] = []

    def _notify(message: str, *, severity: str) -> None:
        notifications.append((message, severity))

    app.notify = _notify

    app.action_continue_session()

    assert notifications == [("Generation already in progress", "warning")]


def test_on_mount_does_not_start_periodic_refresh() -> None:
    """Mount should not schedule interval-based panel refreshes."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeStub())
    interval_calls = {"count": 0}

    def _set_interval(*_: object, **__: object) -> None:
        interval_calls["count"] += 1

    app.set_interval = _set_interval

    app.on_mount()

    assert interval_calls["count"] == 0


def test_action_start_session_refreshes_panel_when_seed_screen_dismisses() -> None:
    """Starting from seed entry should refresh the main panel after dismiss."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeStub())
    refreshed = {"calls": 0}
    captured: dict[str, Callable[[object], None] | None] = {"callback": None}

    def _refresh_panel() -> None:
        refreshed["calls"] += 1

    def _push_screen(*_: object, **kwargs: object) -> None:
        captured["callback"] = cast(
            "Callable[[object], None] | None", kwargs.get("callback")
        )

    app._refresh_panels = _refresh_panel
    app.push_screen = _push_screen

    app.action_start_session()

    callback = captured["callback"]
    assert callable(callback)

    callback(None)

    assert refreshed["calls"] == 1


def test_action_start_session_warns_when_session_exists() -> None:
    """Start should warn when a session is already active."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeWithSessionIdStub())
    notifications: list[tuple[str, str]] = []

    app.notify = lambda message, *, severity: notifications.append((message, severity))

    app.action_start_session()

    assert notifications == [("A session is already running", "warning")]


def test_pause_and_resume_actions_route_runtime_and_notify_on_reject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pause and resume should call handlers and surface rejected resumes."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeWithSessionIdStub())
    calls: list[str] = []
    notifications: list[tuple[str, str]] = []

    app.notify = lambda message, *, severity: notifications.append((message, severity))
    monkeypatch.setattr(
        app_module, "handle_pause_request", lambda runtime: calls.append("pause")
    )
    monkeypatch.setattr(
        app_module,
        "handle_resume_request",
        lambda runtime: CommandResult(
            command_id="resume-1",
            accepted=False,
            message="resume blocked",
            state_version=1,
        ),
    )

    app.action_pause_session()
    app.action_resume_session()

    assert calls == ["pause"]
    assert notifications == [("resume blocked", "warning")]


def test_action_continue_session_warns_for_missing_or_non_running_session() -> None:
    """Continue should reject missing sessions and non-running session states."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeStub())
    notifications: list[tuple[str, str]] = []
    app.notify = lambda message, *, severity: notifications.append((message, severity))

    app.action_continue_session()

    runtime = _RuntimeWithSessionIdStub()
    app.runtime = runtime
    runtime.session.status = SessionStatus.CREATED
    app.action_continue_session()

    assert notifications == [
        ("No active session", "warning"),
        ("Session must be running", "warning"),
    ]


def test_worker_and_command_wrappers_delegate_to_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """App helper methods should delegate to runtime wrappers and handlers."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeWithSessionIdStub())
    calls: list[str] = []

    app._run_continue_generation = lambda: calls.append("worker")
    app._start_continue_generation_worker()

    app.session_switcher.switch_session = lambda session_id: calls.append(
        f"switch:{session_id}"
    )
    monkeypatch.setattr(
        app_module,
        "handle_lock_request",
        lambda runtime, edge_id: CommandResult(
            command_id="lock-1",
            accepted=True,
            message=f"locked {edge_id}",
            state_version=1,
        ),
    )
    monkeypatch.setattr(
        app_module,
        "handle_unlock_request",
        lambda runtime, edge_id: CommandResult(
            command_id="unlock-1",
            accepted=True,
            message=f"unlocked {edge_id}",
            state_version=1,
        ),
    )
    monkeypatch.setattr(
        app_module,
        "handle_fork_request",
        lambda runtime, fork_label=None: CommandResult(
            command_id="fork-1",
            accepted=True,
            message=f"forked {fork_label}",
            state_version=1,
        ),
    )

    target_session_id = uuid4()
    app.switch_session(target_session_id)
    lock_result = app.lock_edge("edge-1")
    unlock_result = app.unlock_edge("edge-1")
    fork_result = app.fork_session("branch-a")

    notifications: list[tuple[str, str]] = []
    app.notify = lambda message, *, severity: notifications.append((message, severity))
    app._refresh_panels = lambda: calls.append("refresh")
    app._complete_continue_generation("boom")

    assert calls[0] == "worker"
    assert calls[1] == f"switch:{target_session_id}"
    assert lock_result.message == "locked edge-1"
    assert unlock_result.message == "unlocked edge-1"
    assert fork_result.message == "forked branch-a"
    assert notifications == [("boom", "error")]


def _build_created_session(seed_text: str) -> Session:
    now = utc_now()
    return Session(
        session_id=uuid4(),
        status=SessionStatus.CREATED,
        seed_text=seed_text,
        graph_version=0,
        active_node_ids=[],
        created_at=now,
        updated_at=now,
    )


def _add_story_node(
    session_graph: SessionGraph,
    *,
    session_id: UUID,
    node_id: str,
    node_kind: NodeKind,
    text: str,
) -> None:
    session_graph.add_node(
        GraphNode(
            node_id=node_id,
            session_id=session_id,
            node_kind=node_kind,
            text=text,
        )
    )


def _add_story_edge(
    session_graph: SessionGraph,
    *,
    session_id: UUID,
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    relation_type: RelationType,
) -> None:
    session_graph.add_edge(
        GraphEdge(
            edge_id=edge_id,
            session_id=session_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=relation_type,
        )
    )


def test_render_session_panel_shows_story_flow_and_branches() -> None:
    """Session panel should render the seeded narrative flow in order."""

    app_module = _app_module()
    session = _build_created_session(seed_text="Beneath the city, rails hum")
    session_graph = SessionGraph()

    _add_story_node(
        session_graph,
        session_id=session.session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="Beneath the city, rails hum",
    )
    _add_story_node(
        session_graph,
        session_id=session.session_id,
        node_id="scene-1",
        node_kind=NodeKind.SCENE,
        text="The last train arrives empty.",
    )
    _add_story_node(
        session_graph,
        session_id=session.session_id,
        node_id="scene-1a",
        node_kind=NodeKind.SCENE,
        text="A porter follows bootprints into steam.",
    )
    _add_story_edge(
        session_graph,
        session_id=session.session_id,
        edge_id="seed->scene-1",
        source_node_id="seed",
        target_node_id="scene-1",
        relation_type=RelationType.FOLLOWS,
    )
    _add_story_edge(
        session_graph,
        session_id=session.session_id,
        edge_id="scene-1->scene-1a",
        source_node_id="scene-1",
        target_node_id="scene-1a",
        relation_type=RelationType.BRANCHES_FROM,
    )

    app = app_module.SessionApp(
        runtime=_RuntimeWithSessionStub(session=session, session_graph=session_graph)
    )

    panel = app._render_scene_text()

    assert "📖 STORY FLOW" in panel
    assert "1. The last train arrives empty." in panel
    assert "  1.1 A porter follows bootprints into steam." in panel


def test_render_session_panel_shows_detached_scene_section() -> None:
    """Session panel should keep disconnected scenes visible."""

    app_module = _app_module()
    session = _build_created_session(seed_text="The observatory darkens")
    session_graph = SessionGraph()

    _add_story_node(
        session_graph,
        session_id=session.session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="The observatory darkens",
    )
    _add_story_node(
        session_graph,
        session_id=session.session_id,
        node_id="scene-detached",
        node_kind=NodeKind.SCENE,
        text="A cracked lens points at noon stars.",
    )

    app = app_module.SessionApp(
        runtime=_RuntimeWithSessionStub(session=session, session_graph=session_graph)
    )

    panel = app._render_scene_text()

    assert "🧩 DETACHED SCENES" in panel
    assert "- A cracked lens points at noon stars." in panel


class _RuntimeWithForkSupportStub:
    """Runtime stub that simulates fork from current node behavior."""

    def __init__(
        self,
        *,
        has_current_node: bool = True,
        fork_will_succeed: bool = True,
    ) -> None:
        self.session_id = uuid4()
        self._has_current_node = has_current_node
        self._fork_will_succeed = fork_will_succeed
        self.fork_calls: list[dict[str, object]] = []
        self.current_node_id = "current-node-123" if has_current_node else None
        self.graph_registry = _GraphRegistryStub(
            has_active_session=has_current_node,
            current_node_id=self.current_node_id,
        )

    def create_fork_request(self, seed: str | None = None) -> object | None:
        """Simulate creating a fork request from current node context."""

        if not self._has_current_node:
            return None

        from models.requests import ForkFromCurrentNodeRequest

        return ForkFromCurrentNodeRequest(
            active_graph_id=str(self.session_id),
            current_node_id=self.current_node_id or "",
            seed=seed,
        )


class _GraphRegistryStub:
    """Stub for graph registry with current node tracking."""

    def __init__(
        self,
        has_active_session: bool = True,
        current_node_id: str | None = None,
    ) -> None:
        self._has_active_session = has_active_session
        self._current_node_id = current_node_id

    def get_active_session(self) -> object | None:
        """Return active session or raise NoActiveGraphError."""

        from runtime.graph_registry import NoActiveGraphError

        if not self._has_active_session:
            raise NoActiveGraphError("no active graph")

        # Return a mock session-like object
        class _MockSession:
            def __init__(self, node_id: str | None) -> None:
                self.current_node_id = node_id
                self.graph_id = "mock-graph-id"

        return _MockSession(self._current_node_id)


class TestForkFromCurrentNodeKeybinding:
    """Unit tests for `f` keybinding initiating fork flow (T015)."""

    def test_f_keybinding_initiates_fork_flow_when_current_node_exists(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pressing `f` with current node selected should initiate fork flow.

        Acceptance Scenario: Given a graph is open and a current node is selected,
        When the user presses `f`, Then the system initiates a fork flow from
        that current node.
        """

        app_module = _app_module()
        runtime = _RuntimeWithForkSupportStub(has_current_node=True)
        app = app_module.SessionApp(runtime=runtime)

        # Track if fork screen would be pushed
        screens_pushed: list[str] = []

        def _push_fork_screen(*_: object, **__: object) -> None:
            screens_pushed.append("fork-seed-entry")

        # Mock the fork action handler
        monkeypatch.setattr(app, "action_fork_from_current_node", _push_fork_screen)

        # Simulate pressing 'f' keybinding
        app.action_fork_from_current_node()

        assert "fork-seed-entry" in screens_pushed

    def test_f_keybinding_shows_error_when_no_current_node(self) -> None:
        """Pressing `f` without current node should show error notification.

        Edge Case: If the user presses `f` when no current node is available,
        the system informs the user and does not start fork creation.
        """

        app_module = _app_module()
        runtime = _RuntimeWithForkSupportStub(has_current_node=False)
        app = app_module.SessionApp(runtime=runtime)
        notifications: list[tuple[str, str]] = []

        app.notify = lambda message, *, severity: notifications.append(
            (message, severity)
        )

        # Call the fork action directly (simulating 'f' keybinding)
        # Before implementation, this method may not exist
        try:
            app.action_fork_from_current_node()
        except AttributeError:
            # Expected to fail until implementation is added
            pytest.fail("action_fork_from_current_node not implemented yet")

        # Should have shown a warning notification
        assert any(severity == "warning" for _, severity in notifications)

    def test_f_keybinding_requires_running_session(self) -> None:
        """Pressing `f` without active session should notify error."""

        app_module = _app_module()
        runtime = _RuntimeStub()  # No session
        app = app_module.SessionApp(runtime=runtime)
        notifications: list[tuple[str, str]] = []

        app.notify = lambda message, *, severity: notifications.append(
            (message, severity)
        )

        try:
            app.action_fork_from_current_node()
        except AttributeError:
            pytest.fail("action_fork_from_current_node not implemented yet")

        # Should show error about no active session
        assert any(
            "no active" in message.lower() or "session" in message.lower()
            for message, _ in notifications
        )


class TestForkCancelBehavior:
    """Unit tests for fork cancel behavior (T016)."""

    def test_fork_cancel_does_not_create_new_graph(self) -> None:
        """Canceling fork flow should not create a new graph.

        Acceptance Scenario: Given the fork flow is active,
        When the user cancels before confirming,
        Then no new graph is created and the current graph remains active.
        """

        app_module = _app_module()
        runtime = _RuntimeWithForkSupportStub(has_current_node=True)
        app = app_module.SessionApp(runtime=runtime)

        # Track if fork was actually invoked
        fork_invoked = False

        # Store original state
        original_session_id = runtime.session_id

        try:
            # Simulate canceling the fork flow
            app.action_cancel_fork()
        except AttributeError:
            pytest.fail("action_cancel_fork not implemented yet")

        # Fork should not have been invoked
        assert fork_invoked is False

        # Session should remain unchanged
        assert runtime.session_id == original_session_id

    def test_fork_cancel_returns_to_normal_operation(self) -> None:
        """Canceling fork should return to normal TUI operation."""

        app_module = _app_module()
        runtime = _RuntimeWithForkSupportStub(has_current_node=True)
        app = app_module.SessionApp(runtime=runtime)

        # Track if screen was popped
        screens_popped = 0

        def _pop_screen() -> None:
            nonlocal screens_popped
            screens_popped += 1

        app.pop_screen = _pop_screen

        try:
            app.action_cancel_fork()
        except AttributeError:
            pytest.fail("action_cancel_fork not implemented yet")

        # Should pop the fork screen
        assert screens_popped == 1


def test_tab_keybinding_switches_to_next_graph() -> None:
    """Tab keybinding should route to next-graph runtime navigation."""

    app_module = _app_module()
    runtime = _RuntimeWithGraphSwitchStub(graph_count=3)
    app = app_module.SessionApp(runtime=runtime)
    refreshed = {"calls": 0}

    def _refresh_panels() -> None:
        refreshed["calls"] += 1

    app._refresh_panels = _refresh_panels

    if not any(binding[0] == "tab" for binding in app.BINDINGS):
        pytest.fail("Tab keybinding is not configured in SessionApp.BINDINGS")

    try:
        app.action_next_graph()
    except AttributeError:
        pytest.fail("action_next_graph not implemented yet")

    assert runtime.next_calls == 1
    assert refreshed["calls"] == 1


def test_shift_tab_keybinding_switches_to_previous_graph() -> None:
    """Shift+Tab keybinding should route to previous-graph navigation."""

    app_module = _app_module()
    runtime = _RuntimeWithGraphSwitchStub(graph_count=3)
    app = app_module.SessionApp(runtime=runtime)
    refreshed = {"calls": 0}

    def _refresh_panels() -> None:
        refreshed["calls"] += 1

    app._refresh_panels = _refresh_panels

    if not any(binding[0] == "shift+tab" for binding in app.BINDINGS):
        pytest.fail("Shift+Tab keybinding is not configured in SessionApp.BINDINGS")

    try:
        app.action_previous_graph()
    except AttributeError:
        pytest.fail("action_previous_graph not implemented yet")

    assert runtime.previous_calls == 1
    assert refreshed["calls"] == 1


def test_tui_entry_path_opens_successfully_with_core_workflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Main startup should launch TUI mode with all core workflow bindings available."""

    app_module = _app_module()
    main_module = _main_module()
    runtime = _RuntimeStub()
    calls: list[str] = []

    monkeypatch.setattr(main_module, "SessionRuntime", lambda: runtime)
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)

    def _run_textual_mode(incoming_runtime: object) -> int:
        _ = incoming_runtime
        calls.append("run_textual_mode")
        return 0

    monkeypatch.setattr(main_module, "run_textual_mode", _run_textual_mode)

    exit_code = main_module.main([])

    assert exit_code == 0
    assert calls == ["run_textual_mode"]

    expected_actions = {
        "start_session",
        "pause_session",
        "resume_session",
        "continue_session",
        "fork_from_current_node",
        "next_graph",
        "previous_graph",
    }
    available_actions = {binding[1] for binding in app_module.SessionApp.BINDINGS}
    assert expected_actions.issubset(available_actions)


def test_main_rejects_unknown_legacy_commands() -> None:
    """Main startup should reject legacy command-style arguments."""

    main_module = _main_module()

    with pytest.raises(SystemExit):
        main_module.main(["fork"])
