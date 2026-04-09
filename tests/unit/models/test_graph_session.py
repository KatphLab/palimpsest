"""Tests for the GraphSession model and ExecutionStatus enum."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.execution import ExecutionStatus
from models.graph_session import GraphSession


class TestGraphSession:
    """Tests for GraphSession entity."""

    def test_graph_session_accepts_valid_data(self) -> None:
        """GraphSession should accept valid UUID and execution status."""
        session = GraphSession(
            graph_id="550e8400-e29b-41d4-a716-446655440000",
            current_node_id="node-1",
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )

        assert session.graph_id == "550e8400-e29b-41d4-a716-446655440000"
        assert session.current_node_id == "node-1"
        assert session.execution_status == ExecutionStatus.RUNNING
        assert session.is_active is True

    def test_graph_session_accepts_optional_current_node_id(self) -> None:
        """GraphSession should allow null current_node_id."""
        session = GraphSession(
            graph_id="550e8400-e29b-41d4-a716-446655440000",
            current_node_id=None,
            execution_status=ExecutionStatus.IDLE,
            is_active=False,
        )

        assert session.current_node_id is None
        assert session.execution_status == ExecutionStatus.IDLE

    def test_graph_session_rejects_invalid_uuid(self) -> None:
        """GraphSession should reject non-UUID graph_id."""
        with pytest.raises(ValidationError) as exc_info:
            GraphSession(
                graph_id="not-a-uuid",
                execution_status=ExecutionStatus.IDLE,
            )

        assert "graph_id" in str(exc_info.value)

    def test_graph_session_rejects_blank_current_node_id(self) -> None:
        """GraphSession should reject empty current_node_id when provided."""
        with pytest.raises(ValidationError) as exc_info:
            GraphSession(
                graph_id="550e8400-e29b-41d4-a716-446655440000",
                current_node_id="   ",
                execution_status=ExecutionStatus.IDLE,
            )

        assert "current_node_id" in str(exc_info.value)

    def test_graph_session_defaults(self) -> None:
        """GraphSession should have sensible defaults."""
        session = GraphSession(
            graph_id="550e8400-e29b-41d4-a716-446655440000",
        )

        assert session.current_node_id is None
        assert session.execution_status == ExecutionStatus.IDLE
        assert session.is_active is False
        assert session.last_activity_at is not None

    def test_execution_status_enum_values(self) -> None:
        """ExecutionStatus should have expected enum values."""
        assert ExecutionStatus.IDLE.value == "idle"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.PAUSED.value == "paused"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
