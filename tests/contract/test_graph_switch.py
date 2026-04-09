"""Contract tests for GraphSwitchRequest per TUI Multi-Graph Control Contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.requests import GraphNavigationDirection, GraphSwitchRequest


def test_graph_switch_request_accepts_valid_payload() -> None:
    """GraphSwitchRequest should accept valid target graph ID and direction."""

    request = GraphSwitchRequest.model_validate(
        {
            "target_graph_id": "550e8400-e29b-41d4-a716-446655440000",
            "direction": "next",
            "preserve_current": True,
        }
    )

    assert request.target_graph_id == "550e8400-e29b-41d4-a716-446655440000"
    assert request.direction == GraphNavigationDirection.NEXT
    assert request.preserve_current is True


def test_graph_switch_request_accepts_previous_direction() -> None:
    """GraphSwitchRequest should accept 'previous' as valid direction."""

    request = GraphSwitchRequest.model_validate(
        {
            "target_graph_id": "550e8400-e29b-41d4-a716-446655440000",
            "direction": "previous",
        }
    )

    assert request.direction == GraphNavigationDirection.PREVIOUS


def test_graph_switch_request_requires_valid_uuid() -> None:
    """GraphSwitchRequest should reject invalid UUID format."""

    with pytest.raises(ValidationError) as exc_info:
        GraphSwitchRequest.model_validate(
            {
                "target_graph_id": "not-a-valid-uuid",
                "direction": "next",
            }
        )

    assert "target_graph_id" in str(exc_info.value)


def test_graph_switch_request_rejects_invalid_direction() -> None:
    """GraphSwitchRequest should reject invalid navigation direction."""

    with pytest.raises(ValidationError) as exc_info:
        GraphSwitchRequest.model_validate(
            {
                "target_graph_id": "550e8400-e29b-41d4-a716-446655440000",
                "direction": "invalid_direction",
            }
        )

    assert "direction" in str(exc_info.value)


def test_graph_switch_request_direction_is_optional() -> None:
    """GraphSwitchRequest should allow direction to be None."""

    request = GraphSwitchRequest.model_validate(
        {
            "target_graph_id": "550e8400-e29b-41d4-a716-446655440000",
        }
    )

    assert request.direction is None
    assert request.preserve_current is True  # Default value


def test_graph_navigation_direction_enum_values() -> None:
    """GraphNavigationDirection should have correct enum values."""

    assert GraphNavigationDirection.NEXT.value == "next"
    assert GraphNavigationDirection.PREVIOUS.value == "previous"


def test_graph_switch_request_minimal_payload() -> None:
    """GraphSwitchRequest should work with minimal required fields."""

    request = GraphSwitchRequest(
        target_graph_id="550e8400-e29b-41d4-a716-446655440000",
    )

    assert request.target_graph_id == "550e8400-e29b-41d4-a716-446655440000"
    assert request.direction is None
    assert request.preserve_current is True
