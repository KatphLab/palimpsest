"""Contract tests for graph forking request/response schemas."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.multi_graph_view import GraphSummary
from models.requests import GraphForkRequest
from models.responses import EdgeReference, GraphForkResponse


def test_graph_fork_request_accepts_contract_fields() -> None:
    """Fork requests should accept the required contract payload fields."""

    request = GraphForkRequest.model_validate(
        {
            "source_graph_id": "550e8400-e29b-41d4-a716-446655440000",
            "fork_edge_id": "edge_42",
            "custom_seed": "seed_1",
            "label": "Left branch",
        }
    )

    payload = request.model_dump()
    assert payload["source_graph_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["fork_edge_id"] == "edge_42"
    assert payload["custom_seed"] == "seed_1"
    assert payload["label"] == "Left branch"


def test_graph_fork_request_rejects_unexpected_fields() -> None:
    """Fork requests should reject fields outside the contract schema."""

    with pytest.raises(ValidationError):
        GraphForkRequest.model_validate(
            {
                "source_graph_id": "550e8400-e29b-41d4-a716-446655440000",
                "fork_edge_id": "edge_42",
                "extra": True,
            }
        )


def test_graph_fork_response_emits_contract_aliases() -> None:
    """Fork responses should serialize using contract field aliases."""

    summary = GraphSummary(
        id="660e8400-e29b-41d4-a716-446655440000",
        name="Fork graph",
        node_count=2,
        edge_count=1,
        created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        fork_source="550e8400-e29b-41d4-a716-446655440000",
        current_state="Decision point reached.",
        last_modified=datetime(2026, 4, 8, 10, 1, tzinfo=timezone.utc),
    )

    response = GraphForkResponse(
        forked_graph_id="660e8400-e29b-41d4-a716-446655440000",
        fork_point=EdgeReference(
            edge_id="edge_42",
            source_node_id="scene_1",
            target_node_id="scene_2",
        ),
        seed="seed_1",
        creation_time=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        parent_graph_id="550e8400-e29b-41d4-a716-446655440000",
        graph_summary=summary,
    )

    payload = response.model_dump()
    assert payload["forked_graph_id"] == "660e8400-e29b-41d4-a716-446655440000"
    assert payload["fork_point"]["edge_id"] == "edge_42"
    assert payload["parent_graph_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["graph_summary"]["id"] == "660e8400-e29b-41d4-a716-446655440000"


def test_graph_fork_response_requires_contract_fields() -> None:
    """Fork responses should require all contract-mandated fields."""

    with pytest.raises(ValidationError):
        GraphForkResponse.model_validate(
            {"forked_graph_id": "660e8400-e29b-41d4-a716-446655440000"}
        )
