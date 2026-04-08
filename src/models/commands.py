"""Terminal command envelope models and payload contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from models.common import StrictBaseModel

__all__ = [
    "CommandEnvelope",
    "CommandEnvelopeBase",
    "CommandResult",
    "CommandType",
    "EmptyPayload",
    "ExportSessionCommand",
    "ExportSessionPayload",
    "ForkSessionCommand",
    "ForkSessionPayload",
    "InspectNodeCommand",
    "InspectNodePayload",
    "LockEdgeCommand",
    "LockEdgePayload",
    "PauseSessionCommand",
    "QuitCommand",
    "ResumeSessionCommand",
    "StartSessionCommand",
    "StartSessionPayload",
    "TerminalCommand",
    "UnlockEdgeCommand",
    "UnlockEdgePayload",
]

_NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=280),
]


class CommandType(StrEnum):
    """Supported terminal command names."""

    START_SESSION = "start_session"
    PAUSE_SESSION = "pause_session"
    RESUME_SESSION = "resume_session"
    LOCK_EDGE = "lock_edge"
    UNLOCK_EDGE = "unlock_edge"
    FORK_SESSION = "fork_session"
    INSPECT_NODE = "inspect_node"
    EXPORT_SESSION = "export_session"
    QUIT = "quit"


class CommandEnvelopeBase(StrictBaseModel):
    """Common command envelope fields shared by every command."""

    command_id: _NonEmptyText
    session_id: UUID | None = None


class EmptyPayload(StrictBaseModel):
    """Payload for commands that do not require arguments."""


class StartSessionPayload(StrictBaseModel):
    """Payload for the start-session command."""

    seed_text: _SeedText


class LockEdgePayload(StrictBaseModel):
    """Payload for locking an edge."""

    edge_id: _NonEmptyText


class UnlockEdgePayload(StrictBaseModel):
    """Payload for unlocking an edge."""

    edge_id: _NonEmptyText


class ForkSessionPayload(StrictBaseModel):
    """Payload for forking a session."""

    fork_label: _NonEmptyText | None = None


class InspectNodePayload(StrictBaseModel):
    """Payload for node inspection."""

    node_id: _NonEmptyText


class ExportSessionPayload(StrictBaseModel):
    """Payload for export commands."""

    output_path: _NonEmptyText


class StartSessionCommand(CommandEnvelopeBase):
    """Envelope for the start-session command."""

    command_type: Literal[CommandType.START_SESSION]
    payload: StartSessionPayload


class PauseSessionCommand(CommandEnvelopeBase):
    """Envelope for the pause-session command."""

    command_type: Literal[CommandType.PAUSE_SESSION]
    payload: EmptyPayload


class ResumeSessionCommand(CommandEnvelopeBase):
    """Envelope for the resume-session command."""

    command_type: Literal[CommandType.RESUME_SESSION]
    payload: EmptyPayload


class LockEdgeCommand(CommandEnvelopeBase):
    """Envelope for the lock-edge command."""

    command_type: Literal[CommandType.LOCK_EDGE]
    payload: LockEdgePayload


class UnlockEdgeCommand(CommandEnvelopeBase):
    """Envelope for the unlock-edge command."""

    command_type: Literal[CommandType.UNLOCK_EDGE]
    payload: UnlockEdgePayload


class ForkSessionCommand(CommandEnvelopeBase):
    """Envelope for the fork-session command."""

    command_type: Literal[CommandType.FORK_SESSION]
    payload: ForkSessionPayload


class InspectNodeCommand(CommandEnvelopeBase):
    """Envelope for the inspect-node command."""

    command_type: Literal[CommandType.INSPECT_NODE]
    payload: InspectNodePayload


class ExportSessionCommand(CommandEnvelopeBase):
    """Envelope for the export-session command."""

    command_type: Literal[CommandType.EXPORT_SESSION]
    payload: ExportSessionPayload


class QuitCommand(CommandEnvelopeBase):
    """Envelope for the quit command."""

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

TerminalCommand = CommandEnvelope


class CommandResult(StrictBaseModel):
    """Validation result emitted by the runtime after command handling."""

    command_id: _NonEmptyText
    accepted: bool
    session_id: UUID | None = None
    state_version: int | None = Field(default=None, ge=0)
    message: _NonEmptyText
