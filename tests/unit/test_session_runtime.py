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
from runtime.session_runtime import SessionRuntime, _RuntimeEventType


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


def test_session_runtime_discards_old_runtime_events_after_the_buffer_limit() -> None:
    """The runtime should keep only the most recent 1000 events."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    runtime.session_id = UUID(int=1)

    for index in range(1001):
        runtime._append_runtime_event(
            event_type=_RuntimeEventType.LOCK_EDGE,
            command_id=f"cmd-{index:04d}",
            session_id=runtime.session_id,
            message="event",
        )

    events = runtime.runtime_event_buffer

    assert len(events) == 1000
    assert events[0].sequence == 2
    assert events[-1].sequence == 1001


def test_session_runtime_exposes_all_runtime_event_kinds() -> None:
    """The runtime event enum should cover all supported command kinds."""

    assert {member.value for member in _RuntimeEventType} == {
        "add_node",
        "add_edge",
        "remove_edge",
        "rewrite_node",
        "prune_branch",
        "lock_edge",
        "unlock_edge",
        "fork_session",
    }
