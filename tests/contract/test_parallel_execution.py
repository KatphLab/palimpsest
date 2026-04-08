"""Contract tests for parallel execution models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.execution import ExecutionState, ParallelExecutionState


def _execution_payload(*, graph_id: str) -> dict[str, object]:
    return {
        "graphId": graph_id,
        "status": "running",
        "currentNodeId": "node-1",
        "completedNodes": 1,
        "totalNodes": 4,
        "progress": 0.25,
        "startedAt": datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc),
        "lastActivity": datetime(2026, 4, 8, 12, 1, tzinfo=timezone.utc),
    }


def test_execution_state_accepts_contract_field_aliases() -> None:
    """ExecutionState should deserialize and serialize contract aliases."""

    state = ExecutionState.model_validate(
        _execution_payload(graph_id="550e8400-e29b-41d4-a716-446655440000")
    )
    payload = state.model_dump(by_alias=True)

    assert payload["graphId"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["status"] == "running"
    assert payload["completedNodes"] == 1
    assert payload["progress"] == 0.25


def test_parallel_execution_state_rejects_more_than_50_executions() -> None:
    """ParallelExecutionState should enforce contract max_length=50."""

    payload = {
        "executions": [
            _execution_payload(
                graph_id=f"550e8400-e29b-41d4-a716-{index:012d}",
            )
            for index in range(51)
        ],
        "activeCount": 51,
        "maxParallel": 50,
    }

    with pytest.raises(ValidationError):
        ParallelExecutionState.model_validate(payload)
