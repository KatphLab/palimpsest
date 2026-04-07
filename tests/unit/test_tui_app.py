"""Unit tests for the TUI app shell."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from types import ModuleType
from typing import Callable, cast
from uuid import UUID, uuid4

from textual.widgets import Static

from graph.session_graph import SessionGraph
from models.common import NodeKind, RelationType, SessionStatus
from models.graph import GraphEdge, GraphNode
from models.session import Session


def _app_module() -> ModuleType:
    return import_module("tui.app")


class _RuntimeStub:
    def __init__(self) -> None:
        self.session_id = None


class _RuntimeWithSessionStub:
    def __init__(self, *, session: Session, session_graph: SessionGraph) -> None:
        self.session_id = session.session_id
        self.session = session
        self.session_graph = session_graph
        self.state_version = 2


class _StaticPanelSpy:
    def __init__(self) -> None:
        self.contents: list[str] = []

    def update(self, content: str) -> None:
        self.contents.append(content)


def test_refresh_active_session_panel_updates_text_only() -> None:
    """Refreshing should update content without forcing scroll movement."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeStub())
    panel = _StaticPanelSpy()
    app._render_session_panel = lambda: "updated content"

    def _query_one(selector: str, widget_type: type[object]) -> object:
        if selector == "#active-session-panel" and widget_type is Static:
            return panel
        raise AssertionError(f"Unexpected query selector={selector} type={widget_type}")

    app.query_one = _query_one

    app._refresh_active_session_panel()

    assert panel.contents == ["updated content"]


def test_action_continue_session_runs_manual_cycle_and_refreshes_panel() -> None:
    """Continue should trigger one manual cycle and one panel refresh."""

    app_module = _app_module()

    class _RuntimeContinueStub:
        def __init__(self) -> None:
            self.session_id = uuid4()
            self.session = _build_created_session(seed_text="seed")
            self.session.status = SessionStatus.RUNNING
            self.advance_calls = 0

        def advance_session_cycle(self) -> None:
            self.advance_calls += 1
            return None

    runtime = _RuntimeContinueStub()
    app = app_module.SessionApp(runtime=runtime)
    refreshed = {"calls": 0}

    def _refresh_panel() -> None:
        refreshed["calls"] += 1

    app._refresh_active_session_panel = _refresh_panel

    app.action_continue_session()

    assert runtime.advance_calls == 1
    assert refreshed["calls"] == 1


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

    app._refresh_active_session_panel = _refresh_panel
    app.push_screen = _push_screen

    app.action_start_session()

    callback = captured["callback"]
    assert callable(callback)

    callback(None)

    assert refreshed["calls"] == 1


def _build_created_session(seed_text: str) -> Session:
    now = datetime.now(timezone.utc)
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

    panel = app._render_session_panel()

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

    panel = app._render_session_panel()

    assert "🧩 DETACHED SCENES" in panel
    assert "- A cracked lens points at noon stars." in panel
