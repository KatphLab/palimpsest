"""Tests for the session graph service skeleton."""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from graph.session_graph import SessionGraph
from models.common import NodeKind, ProtectionReason, RelationType
from models.graph import GraphEdge, GraphNode


class _FixedUtcNow:
    """Deterministic utc_now provider for timestamp tests."""

    values: list[datetime] = []
    index = 0

    @classmethod
    def utc_now(cls) -> datetime:
        value = cls.values[min(cls.index, len(cls.values) - 1)]
        cls.index += 1
        return value


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


def test_session_graph_sets_and_updates_edge_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edge timestamps should be set on add and updated on mutation."""

    created_at = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)
    locked_at = datetime(2026, 4, 7, 0, 0, 1, tzinfo=timezone.utc)
    unlocked_at = datetime(2026, 4, 7, 0, 0, 2, tzinfo=timezone.utc)
    _FixedUtcNow.values = [created_at, locked_at, unlocked_at]
    _FixedUtcNow.index = 0
    monkeypatch.setattr("graph.session_graph.utc_now", _FixedUtcNow.utc_now)

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
        edge_id="edge-2",
        session_id=UUID(int=1),
        source_node_id=node_a.node_id,
        target_node_id=node_b.node_id,
        relation_type=RelationType.FOLLOWS,
        created_at=datetime(2026, 4, 6, 23, 59, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 6, 23, 59, tzinfo=timezone.utc),
    )

    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_edge(edge)

    added_edge = graph.get_edge(edge.edge_id)
    assert added_edge is not None
    assert added_edge.created_at == created_at
    assert added_edge.updated_at == created_at

    graph.lock_edge(edge.edge_id)
    locked_edge = graph.get_edge(edge.edge_id)
    assert locked_edge is not None
    assert locked_edge.created_at == created_at
    assert locked_edge.updated_at == locked_at

    graph.unlock_edge(edge.edge_id)
    unlocked_edge = graph.get_edge(edge.edge_id)
    assert unlocked_edge is not None
    assert unlocked_edge.created_at == created_at
    assert unlocked_edge.updated_at == unlocked_at


def test_session_graph_lock_edge_accepts_an_explicit_protection_reason() -> None:
    """Locking should allow the caller to supply a custom reason."""

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
        edge_id="edge-3",
        session_id=UUID(int=1),
        source_node_id=node_a.node_id,
        target_node_id=node_b.node_id,
        relation_type=RelationType.FOLLOWS,
        created_at=datetime(2026, 4, 6, 23, 59, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 6, 23, 59, tzinfo=timezone.utc),
    )

    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_edge(edge)

    graph.lock_edge(edge.edge_id, ProtectionReason.SAFETY_GUARD)

    locked_edge = graph.get_edge(edge.edge_id)
    assert locked_edge is not None
    assert locked_edge.locked is True
    assert locked_edge.protected_reason is ProtectionReason.SAFETY_GUARD
