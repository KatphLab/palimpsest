"""Tests for the StatusSnapshot model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.execution import ExecutionStatus
from models.status_snapshot import StatusSnapshot


class TestStatusSnapshot:
    """Tests for StatusSnapshot entity."""

    def test_status_snapshot_accepts_valid_data(self) -> None:
        """StatusSnapshot should accept valid position and state data."""
        snapshot = StatusSnapshot(
            active_position=2,
            total_graphs=5,
            active_running_state=ExecutionStatus.RUNNING,
        )

        assert snapshot.active_position == 2
        assert snapshot.total_graphs == 5
        assert snapshot.active_running_state == ExecutionStatus.RUNNING

    def test_status_snapshot_rejects_position_zero(self) -> None:
        """StatusSnapshot should reject active_position less than 1."""
        with pytest.raises(ValidationError) as exc_info:
            StatusSnapshot(
                active_position=0,
                total_graphs=5,
                active_running_state=ExecutionStatus.IDLE,
            )

        assert "active_position" in str(exc_info.value)

    def test_status_snapshot_rejects_position_exceeding_total(self) -> None:
        """StatusSnapshot should reject active_position > total_graphs."""
        with pytest.raises(ValidationError) as exc_info:
            StatusSnapshot(
                active_position=10,
                total_graphs=5,
                active_running_state=ExecutionStatus.IDLE,
            )

        assert "active_position" in str(exc_info.value)

    def test_status_snapshot_accepts_position_one_with_no_graphs(self) -> None:
        """StatusSnapshot should accept position=1 when total_graphs=0."""
        snapshot = StatusSnapshot(
            active_position=1,
            total_graphs=0,
            active_running_state=ExecutionStatus.IDLE,
        )

        assert snapshot.active_position == 1
        assert snapshot.total_graphs == 0

    def test_status_snapshot_rejects_position_not_one_with_no_graphs(self) -> None:
        """StatusSnapshot should reject position != 1 when total_graphs=0."""
        with pytest.raises(ValidationError) as exc_info:
            StatusSnapshot(
                active_position=2,
                total_graphs=0,
                active_running_state=ExecutionStatus.IDLE,
            )

        assert "active_position" in str(exc_info.value)

    def test_status_snapshot_rejects_negative_total(self) -> None:
        """StatusSnapshot should reject negative total_graphs."""
        with pytest.raises(ValidationError) as exc_info:
            StatusSnapshot(
                active_position=1,
                total_graphs=-1,
                active_running_state=ExecutionStatus.IDLE,
            )

        assert "total_graphs" in str(exc_info.value)

    def test_status_snapshot_all_execution_states(self) -> None:
        """StatusSnapshot should accept all valid execution states."""
        for status in ExecutionStatus:
            snapshot = StatusSnapshot(
                active_position=1,
                total_graphs=1,
                active_running_state=status,
            )
            assert snapshot.active_running_state == status
