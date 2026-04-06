"""Tests for the session runtime command router skeleton."""

from uuid import UUID

import pytest

from graph.session_graph import SessionGraph
from models.commands import (
    CommandResult,
    CommandType,
    StartSessionCommand,
    StartSessionPayload,
)
from runtime.session_runtime import SessionRuntime


def test_session_runtime_owns_the_session_graph_instance() -> None:
    """The runtime should own the graph service it was given."""

    graph = SessionGraph()

    runtime = SessionRuntime(session_graph=graph)

    assert runtime.session_graph is graph


def test_session_runtime_routes_start_commands_to_the_start_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The router should dispatch a start command to the matching handler."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    command = StartSessionCommand(
        command_id="cmd-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="seed text"),
    )
    expected = CommandResult(
        command_id=command.command_id,
        accepted=True,
        session_id=UUID(int=1),
        state_version=0,
        message="handled",
    )

    def fake_start_handler(incoming_command: StartSessionCommand) -> CommandResult:
        assert incoming_command is command
        return expected

    monkeypatch.setattr(runtime, "_handle_start_session", fake_start_handler)

    result = runtime.handle_command(command)

    assert result is expected
