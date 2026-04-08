"""Integration tests for pause/resume flow."""

from time import sleep

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandType,
    EmptyPayload,
    PauseSessionCommand,
    ResumeSessionCommand,
    StartSessionCommand,
    StartSessionPayload,
)
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider

pytestmark = pytest.mark.integration


def _graph_signature(
    runtime: SessionRuntime,
) -> tuple[
    tuple[tuple[str, tuple[tuple[str, str], ...]], ...],
    tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...],
]:
    node_signature = tuple(
        sorted(
            (
                node_id,
                tuple(sorted((key, repr(value)) for key, value in node_data.items())),
            )
            for node_id, node_data in runtime.session_graph.graph.nodes(data=True)
        )
    )
    edge_signature = tuple(
        sorted(
            (
                source_node_id,
                target_node_id,
                edge_key,
                tuple(sorted((key, repr(value)) for key, value in edge_data.items())),
            )
            for source_node_id, target_node_id, edge_key, edge_data in runtime.session_graph.graph.edges(
                keys=True,
                data=True,
            )
        )
    )
    return node_signature, edge_signature


def test_pause_and_resume_preserve_session_identity_and_graph_state() -> None:
    """Pausing and resuming should preserve the active session state."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    start_command = StartSessionCommand(
        command_id="cmd-start-003",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A clockwork bird pauses mid-song."),
    )
    pause_command = PauseSessionCommand(
        command_id="cmd-pause-003",
        command_type=CommandType.PAUSE_SESSION,
        payload=EmptyPayload(),
    )
    resume_command = ResumeSessionCommand(
        command_id="cmd-resume-003",
        command_type=CommandType.RESUME_SESSION,
        payload=EmptyPayload(),
    )

    start_result = runtime.handle_command(start_command)
    started_signature = _graph_signature(runtime)

    assert start_result.accepted is True
    assert start_result.session_id is not None
    assert runtime.session_id == start_result.session_id
    assert start_result.state_version == 1
    assert runtime.state_version == 1

    pause_result = runtime.handle_command(pause_command)
    paused_signature = _graph_signature(runtime)

    sleep(0.05)

    resume_result = runtime.handle_command(resume_command)
    resumed_signature = _graph_signature(runtime)

    assert pause_result.accepted is True
    assert pause_result.session_id == start_result.session_id
    assert pause_result.state_version == start_result.state_version
    assert paused_signature == started_signature

    assert resume_result.accepted is True
    assert resume_result.session_id == start_result.session_id
    assert resume_result.state_version is not None
    assert pause_result.state_version is not None
    assert resume_result.state_version >= pause_result.state_version
    assert resumed_signature == paused_signature
