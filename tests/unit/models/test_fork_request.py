"""Tests for the ForkRequest model and ForkRequestStatus enum."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.fork_request import ForkRequest, ForkRequestStatus


class TestForkRequest:
    """Tests for ForkRequest entity."""

    def test_fork_request_accepts_valid_data(self) -> None:
        """ForkRequest should accept valid graph and node identifiers."""
        request = ForkRequest(
            active_graph_id="550e8400-e29b-41d4-a716-446655440000",
            current_node_id="node-42",
            seed="custom seed text",
            confirm=True,
            status=ForkRequestStatus.CONFIRMED,
        )

        assert request.active_graph_id == "550e8400-e29b-41d4-a716-446655440000"
        assert request.current_node_id == "node-42"
        assert request.seed == "custom seed text"
        assert request.confirm is True
        assert request.status == ForkRequestStatus.CONFIRMED

    def test_fork_request_accepts_optional_seed(self) -> None:
        """ForkRequest should allow null seed for default behavior."""
        request = ForkRequest(
            active_graph_id="550e8400-e29b-41d4-a716-446655440000",
            current_node_id="node-1",
            seed=None,
            confirm=False,
        )

        assert request.seed is None
        assert request.confirm is False

    def test_fork_request_defaults(self) -> None:
        """ForkRequest should have sensible defaults."""
        request = ForkRequest(
            active_graph_id="550e8400-e29b-41d4-a716-446655440000",
            current_node_id="node-1",
        )

        assert request.seed is None
        assert request.confirm is False
        assert request.status == ForkRequestStatus.DRAFT

    def test_fork_request_rejects_invalid_graph_id(self) -> None:
        """ForkRequest should reject non-UUID active_graph_id."""
        with pytest.raises(ValidationError) as exc_info:
            ForkRequest(
                active_graph_id="not-a-uuid",
                current_node_id="node-1",
            )

        assert "active_graph_id" in str(exc_info.value)

    def test_fork_request_rejects_blank_current_node_id(self) -> None:
        """ForkRequest should reject empty current_node_id."""
        with pytest.raises(ValidationError) as exc_info:
            ForkRequest(
                active_graph_id="550e8400-e29b-41d4-a716-446655440000",
                current_node_id="   ",
            )

        assert "current_node_id" in str(exc_info.value)

    def test_fork_request_rejects_seed_exceeding_max_length(self) -> None:
        """ForkRequest should reject seed longer than 255 characters."""
        with pytest.raises(ValidationError) as exc_info:
            ForkRequest(
                active_graph_id="550e8400-e29b-41d4-a716-446655440000",
                current_node_id="node-1",
                seed="x" * 256,
            )

        assert "seed" in str(exc_info.value)

    def test_fork_request_rejects_blank_seed(self) -> None:
        """ForkRequest should reject whitespace-only seed."""
        with pytest.raises(ValidationError) as exc_info:
            ForkRequest(
                active_graph_id="550e8400-e29b-41d4-a716-446655440000",
                current_node_id="node-1",
                seed="   ",
            )

        assert "seed" in str(exc_info.value)

    def test_fork_request_accepts_seed_at_boundary_length(self) -> None:
        """ForkRequest should accept seed at exactly 255 characters."""
        request = ForkRequest(
            active_graph_id="550e8400-e29b-41d4-a716-446655440000",
            current_node_id="node-1",
            seed="x" * 255,
        )

        assert request.seed is not None
        assert len(request.seed) == 255

    def test_fork_request_status_transitions(self) -> None:
        """ForkRequestStatus should have expected lifecycle states."""
        assert ForkRequestStatus.DRAFT.value == "draft"
        assert ForkRequestStatus.CONFIRMED.value == "confirmed"
        assert ForkRequestStatus.APPLIED.value == "applied"
        assert ForkRequestStatus.CANCELLED.value == "cancelled"
