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
from models.common import MutationActionType
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime, _RuntimeEventType


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for runtime unit tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


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


def test_runtime_falls_back_to_add_node_when_no_mutable_edge_exists() -> None:
    """Runtime should propose/add a node when protected edges block remove-edge."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        refresh_interval_seconds=60,
    )
    runtime._scene_agent._provider = DeterministicSceneGenerationProvider()
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-fallback-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A lantern glows in the storm."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    before_nodes = runtime.session_graph.graph.number_of_nodes()

    decision = runtime.run_mutation_cycle()

    assert decision is not None
    assert decision.accepted is True
    assert decision.action_type is MutationActionType.ADD_NODE
    assert runtime.session_graph.graph.number_of_nodes() > before_nodes


def test_runtime_records_mutation_skip_event_when_no_candidate_exists() -> None:
    """Runtime should emit a lifecycle event when no candidate can be selected."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        refresh_interval_seconds=60,
    )
    runtime._scene_agent._provider = DeterministicSceneGenerationProvider()
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-skip-event-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass gate hums with static."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    runtime.session.active_node_ids = []
    runtime.session_graph.graph.clear()
    before_count = len(runtime.runtime_event_buffer)

    decision = runtime.run_mutation_cycle()

    assert decision is None
    events = runtime.runtime_event_buffer
    assert len(events) == before_count + 1
    assert events[-1].message == "mutation skipped: no activation candidate"
