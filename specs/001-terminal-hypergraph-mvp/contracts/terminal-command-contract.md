# Terminal Command Contract

Boundary: Textual UI or CLI command input -> session runtime command handler.

All commands are Pydantic models. The runtime must reject any payload that includes extra fields, omits required fields, or contains invalid IDs.

## Pydantic shapes

```python
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommandType(StrEnum):
    START_SESSION = "start_session"
    PAUSE_SESSION = "pause_session"
    RESUME_SESSION = "resume_session"
    LOCK_EDGE = "lock_edge"
    UNLOCK_EDGE = "unlock_edge"
    FORK_SESSION = "fork_session"
    INSPECT_NODE = "inspect_node"
    EXPORT_SESSION = "export_session"
    QUIT = "quit"


class CommandEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str
    session_id: UUID | None = None


class StartSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_text: str = Field(min_length=1, max_length=280)


class LockEdgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str


class UnlockEdgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str


class ForkSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fork_label: str | None = None


class InspectNodePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str


class ExportSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_path: str


class StartSessionCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.START_SESSION]
    payload: StartSessionPayload


class PauseSessionCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.PAUSE_SESSION]
    payload: EmptyPayload


class ResumeSessionCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.RESUME_SESSION]
    payload: EmptyPayload


class LockEdgeCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.LOCK_EDGE]
    payload: LockEdgePayload


class UnlockEdgeCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.UNLOCK_EDGE]
    payload: UnlockEdgePayload


class ForkSessionCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.FORK_SESSION]
    payload: ForkSessionPayload


class InspectNodeCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.INSPECT_NODE]
    payload: InspectNodePayload


class ExportSessionCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.EXPORT_SESSION]
    payload: ExportSessionPayload


class QuitCommand(CommandEnvelope):
    model_config = ConfigDict(extra="forbid")

    command_type: Literal[CommandType.QUIT]
    payload: EmptyPayload


CommandEnvelope = Annotated[
    StartSessionCommand
    | PauseSessionCommand
    | ResumeSessionCommand
    | LockEdgeCommand
    | UnlockEdgeCommand
    | ForkSessionCommand
    | InspectNodeCommand
    | ExportSessionCommand
    | QuitCommand,
    Field(discriminator="command_type"),
]
```

## Responses

```python
class CommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str
    accepted: bool
    session_id: UUID | None = None
    state_version: int | None = None
    message: str
```

## Validation rules

- `start_session` requires exactly one `seed_text` field and must enforce the 280-character ceiling.
- `command_type` selects the only valid payload model at parse time; invalid `command_type` and `payload` pairings must fail validation.
- `pause_session`, `resume_session`, and `quit` use an empty payload model.
- `lock_edge` and `unlock_edge` require a valid `edge_id`.
- `fork_session` may include an optional human-readable label, but it must not mutate the original session.
- `inspect_node` requires a valid `node_id` from the active session.
- `export_session` requires a writable file path.

## Requirement coverage

- FR-001/FR-002: `start_session`.
- FR-004: `pause_session` and `resume_session`.
- FR-005/FR-006: `lock_edge` and `unlock_edge`.
- FR-007: `fork_session`.
- FR-010: `inspect_node`.
- FR-011: `export_session`.
