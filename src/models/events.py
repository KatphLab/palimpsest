"""Typed event stream models for runtime audit and UI updates."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from models.common import EventOutcome, StrictBaseModel, UTCDateTime

__all__ = [
    "EventRecord",
    "EventStreamEnvelope",
    "EventType",
    "MutationStreamEvent",
    "SessionEvent",
]

_NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EventType(StrEnum):
    """Event kinds emitted by the runtime event stream."""

    SESSION_STARTED = "session_started"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    NODE_ACTIVATED = "node_activated"
    EDGE_LOCKED = "edge_locked"
    EDGE_UNLOCKED = "edge_unlocked"
    MUTATION_PROPOSED = "mutation_proposed"
    MUTATION_APPLIED = "mutation_applied"
    MUTATION_REJECTED = "mutation_rejected"
    COHERENCE_SAMPLED = "coherence_sampled"
    BUDGET_WARNING = "budget_warning"
    BUDGET_BREACH = "budget_breach"
    TERMINATION_VOTED = "termination_voted"
    SESSION_TERMINATED = "session_terminated"
    EXPORT_CREATED = "export_created"
    ERROR_REPORTED = "error_reported"


class SessionEvent(StrictBaseModel):
    """Typed session event record."""

    event_id: _NonEmptyText
    sequence: int = Field(ge=1)
    session_id: UUID
    event_type: EventType
    occurred_at: UTCDateTime
    actor_id: _NonEmptyText | None = None
    target_ids: list[_NonEmptyText] = Field(default_factory=list)
    message: _NonEmptyText


class MutationStreamEvent(SessionEvent):
    """Session event enriched with mutation metadata."""

    mutation_id: _NonEmptyText | None = None
    outcome: EventOutcome | None = None

    @model_validator(mode="after")
    def _validate_mutation_targets(self) -> MutationStreamEvent:
        if self.event_type is EventType.MUTATION_APPLIED and not self.target_ids:
            raise ValueError("applied mutation events require target_ids")

        return self


EventRecord = SessionEvent | MutationStreamEvent


class EventStreamEnvelope(StrictBaseModel):
    """Append-only event stream payload for one session."""

    session_id: UUID
    latest_sequence: int = Field(ge=0)
    events: list[EventRecord]

    @model_validator(mode="after")
    def _validate_event_stream(self) -> EventStreamEnvelope:
        result = self
        if not self.events:
            if self.latest_sequence != 0:
                raise ValueError(
                    "latest_sequence must be zero when the stream is empty"
                )
        else:
            expected_sequence = 1
            previous_occurred_at: datetime | None = None
            for event in self.events:
                if event.session_id != self.session_id:
                    raise ValueError(
                        "event session_id must match the envelope session_id"
                    )

                if event.sequence != expected_sequence:
                    raise ValueError(
                        "event sequence must increase monotonically without gaps"
                    )

                if (
                    previous_occurred_at is not None
                    and event.occurred_at < previous_occurred_at
                ):
                    raise ValueError(
                        "event timestamps must be monotonically non-decreasing"
                    )

                previous_occurred_at = event.occurred_at
                expected_sequence += 1

            if self.latest_sequence != self.events[-1].sequence:
                raise ValueError("latest_sequence must match the final event sequence")

        return result
