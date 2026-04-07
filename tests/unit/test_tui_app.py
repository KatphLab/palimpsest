"""Unit tests for the TUI app shell."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from types import ModuleType
from uuid import UUID, uuid4

from textual.containers import ScrollableContainer
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


class _ScrollContainerSpy:
    def __init__(self) -> None:
        self.scroll_calls = 0

    def scroll_end(self, *, animate: bool = True) -> None:
        _ = animate
        self.scroll_calls += 1


def test_refresh_active_session_panel_updates_text_and_scrolls_to_latest() -> None:
    """Refreshing should update content and auto-follow the newest text."""

    app_module = _app_module()
    app = app_module.SessionApp(runtime=_RuntimeStub())
    panel = _StaticPanelSpy()
    scroll_container = _ScrollContainerSpy()

    app._render_session_panel = lambda: "updated content"

    def _query_one(selector: str, widget_type: type[object]) -> object:
        if selector == "#active-session-panel" and widget_type is Static:
            return panel
        if selector == "#active-session-scroll" and widget_type is ScrollableContainer:
            return scroll_container
        raise AssertionError(f"Unexpected query selector={selector} type={widget_type}")

    app.query_one = _query_one

    app._refresh_active_session_panel()

    assert panel.contents == ["updated content"]
    assert scroll_container.scroll_calls == 1


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
