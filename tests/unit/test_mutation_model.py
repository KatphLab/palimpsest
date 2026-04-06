"""Tests for US2 mutation proposal and decision contracts."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from models.common import CheckStatus, MutationActionType, SafetyCheckResult


def test_mutation_decision_allows_no_op_without_safety_checks() -> None:
    """No-op decisions should not require safety checks."""

    from models.mutation import MutationDecision

    decision = MutationDecision.model_validate(
        {
            "decision_id": "mutation-001",
            "session_id": UUID("11111111-1111-1111-1111-111111111111"),
            "actor_node_id": "scene-1",
            "target_ids": [],
            "action_type": "no_op",
            "risk_score": 0.0,
            "accepted": True,
            "safety_checks": [],
        }
    )

    assert decision.action_type is MutationActionType.NO_OP
    assert decision.safety_checks == []


def test_mutation_decision_requires_safety_checks_for_real_action() -> None:
    """Non-no-op actions must include at least one safety check."""

    from models.mutation import MutationDecision

    with pytest.raises(ValidationError):
        MutationDecision.model_validate(
            {
                "decision_id": "mutation-002",
                "session_id": UUID("11111111-1111-1111-1111-111111111111"),
                "actor_node_id": "scene-1",
                "target_ids": ["edge-1"],
                "action_type": "remove_edge",
                "risk_score": 0.9,
                "accepted": True,
                "safety_checks": [],
            }
        )


def test_mutation_decision_requires_rejected_reason_when_rejected() -> None:
    """Rejected decisions must explain why they were rejected."""

    from models.mutation import MutationDecision

    with pytest.raises(ValidationError):
        MutationDecision.model_validate(
            {
                "decision_id": "mutation-003",
                "session_id": UUID("11111111-1111-1111-1111-111111111111"),
                "actor_node_id": "scene-1",
                "target_ids": ["edge-1"],
                "action_type": "remove_edge",
                "risk_score": 0.9,
                "accepted": False,
                "safety_checks": [
                    {
                        "check_name": "locked_edge_guard",
                        "status": CheckStatus.FAIL,
                        "message": "edge is locked",
                    }
                ],
            }
        )


def test_mutation_decision_accepts_rejected_reason() -> None:
    """Rejected decisions should accept an explanatory reason."""

    from models.mutation import MutationDecision

    decision = MutationDecision.model_validate(
        {
            "decision_id": "mutation-004",
            "session_id": UUID("11111111-1111-1111-1111-111111111111"),
            "actor_node_id": "scene-1",
            "target_ids": ["edge-1"],
            "action_type": "remove_edge",
            "risk_score": 0.9,
            "accepted": False,
            "rejected_reason": "locked edge",
            "safety_checks": [
                {
                    "check_name": "locked_edge_guard",
                    "status": CheckStatus.FAIL,
                    "message": "edge is locked",
                }
            ],
        }
    )

    assert decision.rejected_reason == "locked edge"
    assert decision.safety_checks == [
        SafetyCheckResult(
            check_name="locked_edge_guard",
            status=CheckStatus.FAIL,
            message="edge is locked",
        )
    ]
