"""Session lifecycle models for the narrative runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from models.common import (
    BudgetTelemetry,
    CoherenceSnapshot,
    SessionStatus,
    StrictBaseModel,
    TerminationVoteState,
    UTCDateTime,
)
from utils.time import utc_now

__all__ = ["Session", "SessionSnapshot", "SceneGenerationProvider"]

_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=280),
]
_NodeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _SessionBase(StrictBaseModel):
    """Common session fields shared by live and frozen session records."""

    session_id: UUID
    status: SessionStatus
    seed_text: _SeedText
    parent_session_id: UUID | None = None
    graph_version: int = Field(default=0, ge=0)
    active_node_ids: list[_NodeId] = Field(default_factory=list)
    created_at: UTCDateTime
    updated_at: UTCDateTime
    ended_at: UTCDateTime | None = None

    @model_validator(mode="after")
    def _validate_active_node_ids(self) -> _SessionBase:
        if len(self.active_node_ids) != len(set(self.active_node_ids)):
            raise ValueError("active_node_ids must be unique")

        return self


class Session(_SessionBase):
    """Mutable live session state owned by the runtime."""

    coherence: CoherenceSnapshot | None = None
    budget: BudgetTelemetry | None = None
    termination: TerminationVoteState | None = None

    @model_validator(mode="after")
    def _validate_live_session(self) -> Session:
        if self.status == SessionStatus.RUNNING:
            if self.coherence is None:
                raise ValueError("running sessions require coherence snapshots")

            if self.budget is None:
                raise ValueError("running sessions require budget telemetry")

            if self.termination is None:
                raise ValueError("running sessions require termination state")

        return self

    def snapshot(self, *, captured_at: UTCDateTime | None = None) -> SessionSnapshot:
        """Create a frozen export-ready copy of the live session."""

        exported_at = captured_at or utc_now()
        return SessionSnapshot.model_validate(
            {
                **self.model_dump(mode="python"),
                "captured_at": exported_at,
            }
        )


class SessionSnapshot(_SessionBase):
    """Frozen export-ready copy of a session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coherence: CoherenceSnapshot | None = None
    budget: BudgetTelemetry | None = None
    termination: TerminationVoteState | None = None
    captured_at: UTCDateTime


class SceneGenerationProvider(ABC):
    """Abstract base for scene generation strategies."""

    @abstractmethod
    def generate_first_scene(self, *, seed_text: str) -> str:
        """Generate a narrative first scene from a seed prompt."""
        ...
