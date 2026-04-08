"""Unit tests for projecting narrative flow in the TUI."""

from __future__ import annotations

from uuid import UUID, uuid4

from graph.session_graph import SessionGraph
from models.common import NodeKind, RelationType, SessionStatus
from models.graph import GraphEdge, GraphNode
from models.session import Session
from tui.story_projection import build_story_lines
from utils.time import utc_now


def _build_session(seed_text: str = "Seed text") -> Session:
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


def _add_node(
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


def _add_edge(
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


def test_build_story_lines_orders_seed_and_mainline_flow() -> None:
    """Projection should render seed first, then follows flow."""

    session = _build_session(seed_text="A quiet harbor at dawn")
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A quiet harbor at dawn",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1",
        node_kind=NodeKind.SCENE,
        text="Boats drift in from the fog.",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-2",
        node_kind=NodeKind.SCENE,
        text="A bell rings from the lighthouse.",
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="seed->scene-1",
        source_node_id="seed",
        target_node_id="scene-1",
        relation_type=RelationType.FOLLOWS,
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="scene-1->scene-2",
        source_node_id="scene-1",
        target_node_id="scene-2",
        relation_type=RelationType.FOLLOWS,
    )

    lines = build_story_lines(session_graph=session_graph, session=session)

    assert lines == [
        "----------------------------------------",
        "🌱 SEED",
        "A quiet harbor at dawn",
        "",
        "----------------------------------------",
        "📖 STORY FLOW",
        "1. Boats drift in from the fog.",
        "2. A bell rings from the lighthouse.",
        "",
    ]


def test_build_story_lines_renders_branches_with_indentation() -> None:
    """Projection should show branch scenes under their parent scene."""

    session = _build_session(seed_text="A market hums")
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A market hums",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1",
        node_kind=NodeKind.SCENE,
        text="A vendor raises her lantern.",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1a",
        node_kind=NodeKind.SCENE,
        text="A child follows a stray kite.",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1b",
        node_kind=NodeKind.SCENE,
        text="Rain begins to bead on stone.",
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="seed->scene-1",
        source_node_id="seed",
        target_node_id="scene-1",
        relation_type=RelationType.FOLLOWS,
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="scene-1->scene-1a",
        source_node_id="scene-1",
        target_node_id="scene-1a",
        relation_type=RelationType.BRANCHES_FROM,
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="scene-1->scene-1b",
        source_node_id="scene-1",
        target_node_id="scene-1b",
        relation_type=RelationType.BRANCHES_FROM,
    )

    lines = build_story_lines(session_graph=session_graph, session=session)

    assert "1. A vendor raises her lantern." in lines
    assert "  1.1 A child follows a stray kite." in lines
    assert "  1.2 Rain begins to bead on stone." in lines


def test_build_story_lines_handles_cycles_without_duplicates() -> None:
    """Projection should not loop forever when narrative edges cycle."""

    session = _build_session(seed_text="A wheel turns")
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A wheel turns",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-a",
        node_kind=NodeKind.SCENE,
        text="Scene A",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-b",
        node_kind=NodeKind.SCENE,
        text="Scene B",
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="seed->scene-a",
        source_node_id="seed",
        target_node_id="scene-a",
        relation_type=RelationType.FOLLOWS,
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="scene-a->scene-b",
        source_node_id="scene-a",
        target_node_id="scene-b",
        relation_type=RelationType.FOLLOWS,
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="scene-b->scene-a",
        source_node_id="scene-b",
        target_node_id="scene-a",
        relation_type=RelationType.BRANCHES_FROM,
    )

    lines = build_story_lines(session_graph=session_graph, session=session)

    assert lines.count("1. Scene A") == 1
    assert lines.count("2. Scene B") == 1


def test_build_story_lines_lists_detached_scenes() -> None:
    """Projection should keep disconnected scene nodes visible."""

    session = _build_session(seed_text="A forge glows")
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A forge glows",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-connected",
        node_kind=NodeKind.SCENE,
        text="The blacksmith lifts a blade.",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-detached",
        node_kind=NodeKind.SCENE,
        text="A raven watches from a beam.",
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="seed->scene-connected",
        source_node_id="seed",
        target_node_id="scene-connected",
        relation_type=RelationType.FOLLOWS,
    )

    lines = build_story_lines(session_graph=session_graph, session=session)

    assert "🧩 DETACHED SCENES" in lines
    assert "- A raven watches from a beam." in lines
