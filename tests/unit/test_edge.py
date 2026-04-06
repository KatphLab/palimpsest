"""Tests for narrative edge model invariants."""

import pytest
from pydantic import ValidationError

from models.common import ProtectionReason, RelationType
from models.edge import NarrativeEdge


def test_narrative_edge_accepts_unlocked_edges_without_protection_reason() -> None:
    """Unlocked edges may omit protection metadata."""

    edge = NarrativeEdge.model_validate(
        {
            "edge_id": "edge-1",
            "source_node_id": "node-a",
            "target_node_id": "node-b",
            "relation_type": RelationType.FOLLOWS,
            "relation_group_id": "group-1",
            "provenance_event_id": "event-1",
        }
    )

    assert edge.edge_id == "edge-1"
    assert edge.locked is False
    assert edge.protected_reason is None


def test_narrative_edge_rejects_locked_edges_without_protection_reason() -> None:
    """Locked edges must declare why they are protected."""

    with pytest.raises(ValidationError):
        NarrativeEdge.model_validate(
            {
                "edge_id": "edge-2",
                "source_node_id": "node-a",
                "target_node_id": "node-b",
                "relation_type": RelationType.REINFORCES,
                "locked": True,
                "relation_group_id": "group-1",
                "provenance_event_id": "event-2",
            }
        )


def test_narrative_edge_normalizes_user_locked_edges_into_locked_state() -> None:
    """User locks should normalize the edge into a locked state."""

    edge = NarrativeEdge.model_validate(
        {
            "edge_id": "edge-3",
            "source_node_id": "node-a",
            "target_node_id": "node-b",
            "relation_type": RelationType.CONTRADICTS,
            "locked": False,
            "protected_reason": ProtectionReason.USER_LOCK,
            "relation_group_id": "group-1",
            "provenance_event_id": "event-3",
        }
    )

    assert edge.locked is True
    assert edge.protected_reason is ProtectionReason.USER_LOCK
