# Event Stream Contract

Boundary: session runtime -> Textual UI, exporter, and audit log.

The event stream is append-only, strictly ordered, and fully typed with Pydantic discriminated models.
It uses the canonical mutation audit shape from `data-model.md`, but names the transport-only
mutation stream record `MutationStreamEvent` to avoid a schema-name collision.

## Pydantic shapes

```python
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from data_model import EventOutcome  # canonical enum from data-model.md


class EventType(StrEnum):
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


class SessionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    sequence: int
    session_id: UUID
    event_type: EventType
    occurred_at: datetime
    actor_id: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    message: str


class MutationStreamEvent(SessionEvent):
    mutation_id: str | None = None
    outcome: EventOutcome | None = None


EventRecord = SessionEvent | MutationStreamEvent


class EventStreamEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    latest_sequence: int
    events: list[EventRecord]
```

## Validation rules

- `sequence` must increase monotonically for each session.
- `session_id` must be stable across all events in the same stream.
- `occurred_at` must serialize as UTC ISO-8601 text at JSON boundaries.
- `message` is required for every event so the TUI can present a readable log line.
- `target_ids` is the target field.
- `MutationStreamEvent` is wire-compatible with the canonical `data-model.MutationEvent` audit record.
- `MutationStreamEvent.outcome` uses the canonical `EventOutcome` enum (`success`, `blocked`, `warn`, `fail`) and remains optional when no terminal outcome exists.
- Mutation events must include enough actor/target metadata to replay decisions offline.

## Event semantics

- `session_started`: emitted after a valid seed produces the first scene.
- `node_activated`: emitted when a scene node is selected for the next reasoning cycle.
- `mutation_proposed`: emitted before safety filtering.
- `mutation_applied` / `mutation_rejected`: emitted after safety evaluation.
- `coherence_sampled`: emitted on local or global checks.
- `budget_warning` / `budget_breach`: emitted when telemetry crosses thresholds.
- `termination_voted` / `session_terminated`: emitted when majority voting closes the run.
- `export_created`: emitted after a JSON artifact is written.

## Requirement coverage

- FR-003: refreshable stream of live updates.
- FR-008: node telemetry events.
- FR-009: chronological mutation log.
- FR-012/FR-013: safety and consistency-check events.
- FR-014: termination voting and completion events.
- FR-015: budget events.
- CA-001/CA-005: coherence and budget observability.
