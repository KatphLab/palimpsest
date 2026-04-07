"""Tests for the canonical graph edge model."""

from uuid import UUID

from models import GraphEdge
from models.common import ProtectionReason, RelationType


def test_graph_edge_accepts_unlocked_edges_without_protection_reason() -> None:
    """Unlocked edges may omit protection metadata."""

    edge = GraphEdge.model_validate(
        {
            "edge_id": "edge-1",
            "session_id": UUID(int=1),
            "source_node_id": "node-a",
            "target_node_id": "node-b",
            "relation_type": RelationType.FOLLOWS,
        }
    )

    assert edge.edge_id == "edge-1"
    assert edge.locked is False
    assert edge.protected_reason is None


def test_graph_edge_preserves_locked_edges_with_protection_reason() -> None:
    """Locked edges should keep their protection metadata."""

    edge = GraphEdge.model_validate(
        {
            "edge_id": "edge-3",
            "session_id": UUID(int=1),
            "source_node_id": "node-a",
            "target_node_id": "node-b",
            "relation_type": RelationType.CONTRADICTS,
            "locked": True,
            "protected_reason": ProtectionReason.USER_LOCK,
        }
    )

    assert edge.locked is True
    assert edge.protected_reason is ProtectionReason.USER_LOCK
