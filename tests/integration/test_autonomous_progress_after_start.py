"""Integration tests for manual-only progress after startup."""

from time import sleep

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider

pytestmark = pytest.mark.integration


def test_start_session_does_not_advance_graph_without_manual_cycle() -> None:
    """Runtime should remain stable until a manual mutation cycle is requested."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    command = StartSessionCommand(
        command_id="cmd-start-autonomous-progress-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A lighthouse blinks into the fog."),
    )

    result = runtime.handle_command(command)
    assert result.accepted is True

    sleep(0.25)

    assert runtime.state_version == 1
    assert runtime.session_graph.graph.number_of_nodes() == 2
