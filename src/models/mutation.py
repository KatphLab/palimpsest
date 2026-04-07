"""US2 mutation proposal and decision contracts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from models.common import MutationActionType, SafetyCheckResult, StrictBaseModel

__all__ = ["MutationDecision", "MutationProposal"]

_NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MutationProposal(StrictBaseModel):
    """Proposed graph mutation before safety filtering."""

    decision_id: _NonEmptyText
    session_id: UUID
    actor_node_id: _NonEmptyText
    target_ids: list[_NonEmptyText] = Field(default_factory=list)
    action_type: MutationActionType
    risk_score: float = Field(ge=0.0, le=1.0)


class MutationDecision(MutationProposal):
    """Mutation proposal after safety filtering and rejection handling."""

    safety_checks: list[SafetyCheckResult] = Field(default_factory=list)
    accepted: bool
    rejected_reason: str | None = None

    @model_validator(mode="after")
    def _validate_safety_gate(self) -> MutationDecision:
        if self.action_type is not MutationActionType.NO_OP and not self.safety_checks:
            raise ValueError("non-no_op mutation decisions require safety checks")

        if not self.accepted and self.rejected_reason is None:
            raise ValueError("rejected decisions require rejected_reason")

        return self
