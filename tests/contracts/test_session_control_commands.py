"""Contract tests for session control commands."""

from uuid import UUID

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

pytestmark = pytest.mark.contracts


def _runtime() -> SessionRuntime:
    return SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )


def test_start_session_rejects_client_supplied_session_identifier() -> None:
    """A new session must not accept a caller-provided session identifier."""

    runtime = _runtime()
    command = StartSessionCommand(
        command_id="cmd-start-004",
        session_id=UUID(int=1),
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="Seed the story."),
    )

    with pytest.raises(ValueError):
        runtime.handle_command(command)


def test_pause_session_requires_an_active_session() -> None:
    """Pause commands should target an existing session."""

    runtime = _runtime()
    command = PauseSessionCommand(
        command_id="cmd-pause-004",
        command_type=CommandType.PAUSE_SESSION,
        payload=EmptyPayload(),
    )

    with pytest.raises(ValueError):
        runtime.handle_command(command)


def test_resume_session_requires_an_active_session() -> None:
    """Resume commands should target an existing session."""

    runtime = _runtime()
    command = ResumeSessionCommand(
        command_id="cmd-resume-004",
        command_type=CommandType.RESUME_SESSION,
        payload=EmptyPayload(),
    )

    with pytest.raises(ValueError):
        runtime.handle_command(command)
