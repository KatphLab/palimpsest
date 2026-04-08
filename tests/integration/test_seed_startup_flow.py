"""Integration tests for seed startup flow."""

from time import perf_counter

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider

pytestmark = pytest.mark.integration


def test_seed_startup_creates_the_first_scene_within_two_seconds() -> None:
    """A valid seed should activate the session and populate the first scene quickly."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    command = StartSessionCommand(
        command_id="cmd-start-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A quiet room breathes in the dark."),
    )

    started_at = perf_counter()
    result = runtime.handle_command(command)
    elapsed_seconds = perf_counter() - started_at

    assert elapsed_seconds <= 2.0
    assert result.accepted is True
    assert result.session_id is not None
    assert runtime.session_id == result.session_id
    assert result.state_version == 1
    assert runtime.state_version == 1
    assert runtime.session_graph.graph.number_of_nodes() >= 1
