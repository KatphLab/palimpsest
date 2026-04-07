"""Integration tests for autonomous progress immediately after startup."""

from time import sleep

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime

pytestmark = pytest.mark.integration


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for autonomous progress tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


def test_start_session_advances_graph_after_initial_scene_generation() -> None:
    """Runtime should autonomously mutate the graph shortly after startup."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
        refresh_interval_seconds=0.05,
    )
    command = StartSessionCommand(
        command_id="cmd-start-autonomous-progress-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A lighthouse blinks into the fog."),
    )

    result = runtime.handle_command(command)
    assert result.accepted is True

    sleep(0.25)

    assert runtime.state_version > 1
    assert runtime.session_graph.graph.number_of_nodes() > 2
