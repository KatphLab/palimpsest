"""Integration tests for runtime fork/switch event traceability."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandType,
    ForkSessionCommand,
    ForkSessionPayload,
    StartSessionCommand,
    StartSessionPayload,
)
from models.common import SessionStatus
from models.execution import ExecutionStatus
from models.graph_session import GraphSession
from runtime.event_log import EventLog
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider

pytestmark = pytest.mark.integration


def _build_runtime_with_switchable_sessions() -> tuple[SessionRuntime, UUID, UUID]:
    """Create runtime state with two sessions that can be graph-switched."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-runtime-logging",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A branch of mirrored cities"),
        )
    )
    assert start_result.session_id is not None

    first_session_id = start_result.session_id
    first_state = runtime._session_states[first_session_id]
    second_session_id = uuid4()
    runtime._session_states[second_session_id] = first_state.model_copy(
        deep=True,
        update={
            "session": first_state.session.model_copy(
                deep=True,
                update={
                    "session_id": second_session_id,
                    "parent_session_id": first_session_id,
                },
            ),
            "session_graph": SessionGraph(),
            "event_log": EventLog(
                session_id=second_session_id,
                latest_sequence=0,
                events=[],
            ),
        },
    )
    runtime.register_graph_session(
        GraphSession(
            graph_id=str(second_session_id),
            current_node_id=None,
            execution_status=ExecutionStatus.IDLE,
        )
    )
    runtime.activate_session(first_session_id)
    runtime.graph_registry.set_active_session(str(first_session_id))
    return runtime, first_session_id, second_session_id


def test_fork_command_emits_to_runtime_and_event_log_channels() -> None:
    """Fork commands should appear in runtime buffer and command event log."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-fork-logging",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A museum that loops midnight"),
        )
    )
    assert start_result.session_id is not None
    assert runtime.session is not None
    runtime.session.status = SessionStatus.RUNNING

    command_id = "cmd-fork-logging"
    result = runtime.handle_command(
        ForkSessionCommand(
            command_id=command_id,
            command_type=CommandType.FORK_SESSION,
            session_id=start_result.session_id,
            payload=ForkSessionPayload(fork_label="echo branch"),
        )
    )

    assert result.accepted is True
    assert runtime.runtime_event_buffer[-1].event_type.value == "fork_session"
    assert runtime.event_log is not None
    command_events = [
        event
        for event in runtime.event_log.read().events
        if event.actor_id == command_id
    ]
    assert len(command_events) == 1
    assert "fork_session accepted" in command_events[0].message


def test_graph_switch_emits_to_runtime_and_event_log_channels() -> None:
    """Graph switching should append trace events to both log channels."""

    runtime, _, second_session_id = _build_runtime_with_switchable_sessions()

    switched = runtime.switch_to_next_graph()

    assert switched.graph_id == str(second_session_id)
    assert runtime.runtime_event_buffer[-1].event_type.value == "graph_switch"
    assert runtime.event_log is not None
    switch_events = [
        event
        for event in runtime.event_log.read().events
        if event.message.startswith("graph switch next:")
    ]
    assert len(switch_events) == 1
