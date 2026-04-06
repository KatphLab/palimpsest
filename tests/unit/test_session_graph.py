"""Tests for the session graph service skeleton."""

from uuid import UUID

import pytest

from graph.session_graph import GraphEdge, GraphNode, SessionGraph
from models.common import NodeKind, ProtectionReason, RelationType


def test_session_graph_locks_prevent_edge_removal() -> None:
    """Locked edges must remain in the session graph until unlocked."""

    graph = SessionGraph()
    node_a = GraphNode(
        node_id="node-a",
        session_id=UUID(int=1),
        node_kind=NodeKind.SEED,
        text="seed",
    )
    node_b = GraphNode(
        node_id="node-b",
        session_id=UUID(int=1),
        node_kind=NodeKind.SCENE,
        text="scene",
    )
    edge = GraphEdge(
        edge_id="edge-1",
        session_id=UUID(int=1),
        source_node_id=node_a.node_id,
        target_node_id=node_b.node_id,
        relation_type=RelationType.FOLLOWS,
    )

    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_edge(edge)
    graph.lock_edge(edge.edge_id)

    locked_edge = graph.get_edge(edge.edge_id)
    assert locked_edge is not None
    assert locked_edge.locked is True
    assert locked_edge.protected_reason is ProtectionReason.USER_LOCK

    with pytest.raises(ValueError):
        graph.remove_edge(edge.edge_id)

    graph.unlock_edge(edge.edge_id)
    graph.remove_edge(edge.edge_id)

    assert graph.get_edge(edge.edge_id) is None
