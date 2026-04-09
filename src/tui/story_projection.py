"""Projection helpers for rendering narrative flow in the TUI."""

from __future__ import annotations

from collections.abc import Iterable

from graph.session_graph import SessionGraph
from graph.utils import get_graph_edge, get_graph_node, get_node_kind, get_node_text
from models.common import NodeKind, RelationType
from models.graph import GraphEdge
from models.session import Session
from tui.constants import SECTION_DIVIDER

__all__ = ["build_story_lines"]


def build_story_lines(
    *,
    session_graph: SessionGraph,
    session: Session,
    active_position: int | None = None,
    total_graphs: int | None = None,
) -> list[str]:
    """Build a deterministic, human-readable story flow from the session graph."""

    seed_node_id = _seed_node_id(session_graph)
    seed_text = _seed_text(session_graph, seed_node_id, fallback=session.seed_text)
    mainline_node_ids = _mainline_scene_node_ids(session_graph, seed_node_id)

    lines: list[str] = [
        SECTION_DIVIDER,
        "🌱 SEED",
        seed_text,
        "",
        SECTION_DIVIDER,
        "📖 STORY FLOW",
    ]

    if active_position is not None and total_graphs is not None:
        lines.append(f"Graph {active_position}/{total_graphs}")

    visited_scene_ids: set[str] = set()
    for index, node_id in enumerate(mainline_node_ids, start=1):
        scene_text = get_node_text(session_graph, node_id)
        if scene_text is None:
            continue

        lines.append(f"{index}. {scene_text}")
        visited_scene_ids.add(node_id)
        _append_branch_lines(
            lines,
            session_graph=session_graph,
            node_id=node_id,
            prefix=str(index),
            depth=1,
            visited_scene_ids=visited_scene_ids,
        )

    detached_scene_texts = _detached_scene_texts(session_graph, visited_scene_ids)
    if detached_scene_texts:
        lines.extend(["", "🧩 DETACHED SCENES"])
        lines.extend(f"- {scene_text}" for scene_text in detached_scene_texts)

    lines.append("")
    return lines


def _append_branch_lines(
    lines: list[str],
    *,
    session_graph: SessionGraph,
    node_id: str,
    prefix: str,
    depth: int,
    visited_scene_ids: set[str],
) -> None:
    children = list(_branch_targets(session_graph, source_node_id=node_id))
    for child_index, child_id in enumerate(children, start=1):
        if child_id in visited_scene_ids:
            continue

        child_text = get_node_text(session_graph, child_id)
        if child_text is None:
            continue

        child_prefix = f"{prefix}.{child_index}"
        indent = "  " * depth
        lines.append(f"{indent}{child_prefix} {child_text}")
        visited_scene_ids.add(child_id)
        _append_branch_lines(
            lines,
            session_graph=session_graph,
            node_id=child_id,
            prefix=child_prefix,
            depth=depth + 1,
            visited_scene_ids=visited_scene_ids,
        )


def _mainline_scene_node_ids(
    session_graph: SessionGraph, seed_node_id: str | None
) -> list[str]:
    if seed_node_id is None:
        return []

    scene_node_ids: list[str] = []
    visited: set[str] = {seed_node_id}
    current_node_id = seed_node_id

    while True:
        follow_targets = [
            target_id
            for target_id in _follow_targets(
                session_graph, source_node_id=current_node_id
            )
            if target_id not in visited
        ]
        if not follow_targets:
            break

        next_node_id = follow_targets[0]
        if get_node_kind(session_graph, next_node_id) is NodeKind.SCENE:
            scene_node_ids.append(next_node_id)
            visited.add(next_node_id)

        current_node_id = next_node_id

    return scene_node_ids


def _narrative_edges(
    session_graph: SessionGraph,
    *,
    source_node_id: str,
    relation_type: RelationType,
) -> Iterable[GraphEdge]:
    candidate_edges: list[GraphEdge] = []
    for _, target_node_id, _, edge_data in session_graph.graph.out_edges(
        source_node_id, keys=True, data=True
    ):
        edge = get_graph_edge(edge_data)
        if edge is None:
            continue

        if edge.relation_type is not relation_type:
            continue

        if edge.target_node_id != target_node_id:
            continue

        candidate_edges.append(edge)

    return sorted(candidate_edges, key=lambda edge: (edge.created_at, edge.edge_id))


def _follow_targets(
    session_graph: SessionGraph, *, source_node_id: str
) -> Iterable[str]:
    return [
        edge.target_node_id
        for edge in _narrative_edges(
            session_graph,
            source_node_id=source_node_id,
            relation_type=RelationType.FOLLOWS,
        )
    ]


def _branch_targets(
    session_graph: SessionGraph, *, source_node_id: str
) -> Iterable[str]:
    return [
        edge.target_node_id
        for edge in _narrative_edges(
            session_graph,
            source_node_id=source_node_id,
            relation_type=RelationType.BRANCHES_FROM,
        )
    ]


def _seed_node_id(session_graph: SessionGraph) -> str | None:
    seed_ids = [
        node_id
        for node_id in session_graph.graph.nodes
        if get_node_kind(session_graph, node_id) is NodeKind.SEED
    ]
    if not seed_ids:
        return None

    return sorted(seed_ids)[0]


def _seed_text(
    session_graph: SessionGraph, seed_node_id: str | None, *, fallback: str
) -> str:
    if seed_node_id is None:
        return fallback

    seed_text = get_node_text(session_graph, seed_node_id)
    return seed_text if seed_text is not None else fallback


def _detached_scene_texts(
    session_graph: SessionGraph,
    visited_scene_ids: set[str],
) -> list[str]:
    detached: list[tuple[str, str]] = []
    for node_id in session_graph.graph.nodes:
        graph_node = get_graph_node(session_graph, node_id)
        if graph_node is None:
            continue

        if graph_node.node_kind is not NodeKind.SCENE:
            continue

        if node_id in visited_scene_ids:
            continue

        detached.append((graph_node.node_id, graph_node.text))

    return [text for _, text in sorted(detached, key=lambda item: item[0])]
