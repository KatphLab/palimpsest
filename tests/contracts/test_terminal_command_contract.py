"""Contract tests for terminal command envelopes."""

from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from models.commands import CommandEnvelope, StartSessionCommand


def test_terminal_command_union_rejects_mismatched_payload_model() -> None:
    """Command type selection must reject payloads for the wrong command."""

    with pytest.raises(ValidationError):
        TypeAdapter(CommandEnvelope).validate_python(
            {
                "command_id": "cmd-001",
                "session_id": UUID(int=0),
                "command_type": "start_session",
                "payload": {"edge_id": "edge-1"},
            }
        )


def test_start_session_command_forbids_unexpected_fields() -> None:
    """Start-session commands must reject extra fields at the boundary."""

    with pytest.raises(ValidationError):
        StartSessionCommand.model_validate(
            {
                "command_id": "cmd-002",
                "command_type": "start_session",
                "payload": {"seed_text": "seed", "extra": True},
            }
        )
