"""Contract tests for multi-graph view and switch payloads."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.multi_graph_view import GraphSummary
from models.requests import GraphSwitchRequest
from models.responses import GraphSwitchResponse
from models.views import MultiGraphView


def _summary_payload() -> dict[str, object]:
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Root graph",
        "nodeCount": 4,
        "edgeCount": 3,
        "createdAt": datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        "forkSource": None,
        "currentState": "active",
        "lastModified": datetime(2026, 4, 8, 10, 1, tzinfo=timezone.utc),
        "labels": ["root", "p1"],
    }


def test_graph_summary_accepts_contract_payload_shape() -> None:
    """GraphSummary should accept contract field names and constraints."""

    summary = GraphSummary.model_validate(_summary_payload())
    payload = summary.model_dump(by_alias=True)

    assert payload["nodeCount"] == 4
    assert payload["edgeCount"] == 3
    assert payload["currentState"] == "active"


def test_multi_graph_view_rejects_additional_properties() -> None:
    """MultiGraphView should reject payload fields outside contract schema."""

    with pytest.raises(ValidationError):
        MultiGraphView.model_validate(
            {
                "graphs": [_summary_payload()],
                "activeGraphId": "550e8400-e29b-41d4-a716-446655440000",
                "totalCount": 1,
                "filters": {},
                "viewPrefs": {},
                "unexpected": True,
            }
        )


def test_graph_switch_request_accepts_contract_aliases() -> None:
    """Switch request model should deserialize contract-style aliases."""

    request = GraphSwitchRequest.model_validate(
        {
            "targetGraphId": "550e8400-e29b-41d4-a716-446655440001",
            "preserveCurrent": False,
        }
    )

    payload = request.model_dump(by_alias=True)
    assert payload["targetGraphId"] == "550e8400-e29b-41d4-a716-446655440001"
    assert payload["preserveCurrent"] is False


def test_graph_switch_response_emits_contract_aliases() -> None:
    """Switch response should serialize with required contract field aliases."""

    response = GraphSwitchResponse(
        previous_graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_graph_id="550e8400-e29b-41d4-a716-446655440001",
        load_time_ms=42.0,
        graph_summary=GraphSummary.model_validate(_summary_payload()),
    )

    payload = response.model_dump(by_alias=True)
    assert payload["previousGraphId"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["currentGraphId"] == "550e8400-e29b-41d4-a716-446655440001"
    assert payload["loadTimeMs"] == 42.0
    assert payload["graphSummary"]["name"] == "Root graph"
