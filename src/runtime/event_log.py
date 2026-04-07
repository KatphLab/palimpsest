"""Append-only in-memory event log for session audit records."""

from __future__ import annotations

from models.events import EventRecord, EventStreamEnvelope

__all__ = ["EventLog"]


class EventLog(EventStreamEnvelope):
    """Append-only event stream for a single session."""

    @property
    def next_sequence(self) -> int:
        """Return the next available sequence identifier."""

        return self.latest_sequence + 1

    def append(self, event: EventRecord) -> EventRecord:
        """Append an event with a strictly increasing sequence number."""

        self._validate_appendable_event(event)
        stored_event = event.model_copy(deep=True)
        self.events.append(stored_event)
        self.latest_sequence = stored_event.sequence
        return stored_event

    def read(self) -> EventStreamEnvelope:
        """Return a validated snapshot of the current event stream."""

        return EventStreamEnvelope.model_validate(self.model_dump(mode="python"))

    def _validate_appendable_event(self, event: EventRecord) -> None:
        if event.session_id != self.session_id:
            raise ValueError("event session_id must match the log session_id")

        if event.sequence != self.next_sequence:
            raise ValueError("event sequence must increase monotonically without gaps")

        if self.events and event.occurred_at < self.events[-1].occurred_at:
            raise ValueError("event timestamps must be monotonically non-decreasing")
