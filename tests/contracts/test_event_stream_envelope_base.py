"""Contract tests for ordered event stream envelopes."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from models.events import EventStreamEnvelope, EventType, SessionEvent
from utils.time import utc_now


def test_event_stream_envelope_rejects_non_monotonic_sequences() -> None:
    """Event sequences must be strictly increasing with no gaps."""

    with pytest.raises(ValidationError):
        EventStreamEnvelope.model_validate(
            {
                "session_id": UUID(int=1),
                "latest_sequence": 3,
                "events": [
                    {
                        "event_id": "evt-001",
                        "sequence": 1,
                        "session_id": UUID(int=1),
                        "event_type": EventType.SESSION_STARTED,
                        "occurred_at": utc_now(),
                        "message": "started",
                    },
                    {
                        "event_id": "evt-002",
                        "sequence": 3,
                        "session_id": UUID(int=1),
                        "event_type": EventType.NODE_ACTIVATED,
                        "occurred_at": utc_now(),
                        "message": "skipped sequence",
                    },
                ],
            }
        )


def test_session_event_forbids_extra_fields() -> None:
    """Session events must reject extra payload keys."""

    with pytest.raises(ValidationError):
        SessionEvent.model_validate(
            {
                "event_id": "evt-003",
                "sequence": 1,
                "session_id": UUID(int=2),
                "event_type": EventType.SESSION_STARTED,
                "occurred_at": utc_now(),
                "message": "started",
                "unexpected": True,
            }
        )
