"""Scene node models for narrative activation metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from models.common import (
    DriftCategory,
    NodeKind,
    NodeTerminationVote,
    StrictBaseModel,
    UTCDateTime,
)

__all__ = ["SceneNode"]

_NodeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_NodeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SceneNode(StrictBaseModel):
    """Narrative node record with activation and freshness metadata."""

    node_id: _NodeId
    session_id: UUID
    node_kind: NodeKind
    text: _NodeText
    entropy_score: float = Field(default=0.0, ge=0.0, le=1.0)
    drift_category: DriftCategory | None = None
    activation_count: int = Field(default=0, ge=0)
    last_activated_at: UTCDateTime | None = None
    is_seed_protected: bool = False
    termination_vote: NodeTerminationVote | None = None

    @model_validator(mode="after")
    def _validate_activation_metadata(self) -> SceneNode:
        if self.node_kind == NodeKind.SEED:
            self.is_seed_protected = True
        elif self.is_seed_protected:
            raise ValueError("only seed nodes may be seed-protected")

        if self.activation_count == 0:
            if self.last_activated_at is not None:
                raise ValueError(
                    "last_activated_at requires a positive activation_count"
                )
        elif self.last_activated_at is None:
            raise ValueError("last_activated_at is required once a node is activated")

        if self.drift_category is None:
            self.drift_category = self._derive_drift_category()

        return self

    def activate(self, *, activated_at: UTCDateTime | None = None) -> None:
        """Record one node activation with fresh metadata."""

        self.activation_count += 1
        self.last_activated_at = activated_at or datetime.now(timezone.utc)
        self.drift_category = self._derive_drift_category()

    def _derive_drift_category(self) -> DriftCategory:
        if self.entropy_score <= 0.25:
            return DriftCategory.STABLE

        if self.entropy_score <= 0.5:
            return DriftCategory.WATCH

        if self.entropy_score <= 0.75:
            return DriftCategory.VOLATILE

        return DriftCategory.CRITICAL
