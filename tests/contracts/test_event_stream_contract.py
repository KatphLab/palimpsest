"""Contract tests for mutation event stream semantics."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from models.common import EventOutcome
from models.events import EventStreamEnvelope, EventType, MutationStreamEvent


def test_event_stream_envelope_rejects_mutation_events_that_move_backwards_in_time() -> (
    None
):
    """Mutation streams must remain monotonic across emitted event timestamps."""

    started_at = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValidationError):
        EventStreamEnvelope.model_validate(
            {
                "session_id": UUID(int=10),
                "latest_sequence": 2,
                "events": [
                    {
                        "event_id": "evt-001",
                        "sequence": 1,
                        "session_id": UUID(int=10),
                        "event_type": EventType.SESSION_STARTED,
                        "occurred_at": started_at,
                        "message": "started",
                    },
                    {
                        "event_id": "evt-002",
                        "sequence": 2,
                        "session_id": UUID(int=10),
                        "event_type": EventType.MUTATION_APPLIED,
                        "occurred_at": started_at - timedelta(seconds=1),
                        "mutation_id": "mut-001",
                        "outcome": EventOutcome.SUCCESS,
                        "target_ids": ["node-1"],
                        "message": "applied",
                    },
                ],
            }
        )


def test_mutation_stream_event_requires_target_ids_for_applied_mutations() -> None:
    """Applied mutation events must name at least one target node."""

    with pytest.raises(ValidationError):
        MutationStreamEvent.model_validate(
            {
                "event_id": "evt-003",
                "sequence": 3,
                "session_id": UUID(int=11),
                "event_type": EventType.MUTATION_APPLIED,
                "occurred_at": datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
                "mutation_id": "mut-002",
                "outcome": EventOutcome.SUCCESS,
                "target_ids": [],
                "message": "applied",
            }
        )
