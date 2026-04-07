"""Contract tests for topology control commands."""

from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandEnvelope,
    CommandResult,
    CommandType,
    ForkSessionCommand,
    ForkSessionPayload,
    LockEdgeCommand,
    LockEdgePayload,
    StartSessionCommand,
    StartSessionPayload,
    UnlockEdgeCommand,
    UnlockEdgePayload,
)
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime

pytestmark = pytest.mark.contracts


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for contract tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


def _runtime() -> SessionRuntime:
    """Build a runtime with deterministic scene generation."""

    return SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )


def _start_runtime(runtime: SessionRuntime) -> UUID:
    """Start a runtime session and return its session identifier."""

    command = StartSessionCommand(
        command_id="cmd-start-topology-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="Seed the story."),
    )

    result = runtime.handle_command(command)
    assert isinstance(result, CommandResult)
    assert result.session_id is not None
    return result.session_id


def _seed_edge_id(session_id: UUID) -> str:
    """Build the deterministic bootstrap edge identifier."""

    prefix = session_id.hex[:8]
    return f"{prefix}-seed->{prefix}-scene-1"


def test_lock_edge_command_requires_edge_id_and_locks_the_graph_edge() -> None:
    """Lock commands must validate payloads and mutate the target edge."""

    with pytest.raises(ValidationError):
        TypeAdapter(CommandEnvelope).validate_python(
            {
                "command_id": "cmd-lock-topology-001",
                "command_type": "lock_edge",
                "payload": {},
            }
        )

    with pytest.raises(ValidationError):
        TypeAdapter(CommandEnvelope).validate_python(
            {
                "command_id": "cmd-lock-topology-002",
                "command_type": "lock_edge",
                "payload": {"edge_id": "edge-1", "extra": True},
            }
        )

    runtime = _runtime()
    session_id = _start_runtime(runtime)
    edge_id = _seed_edge_id(session_id)

    result = runtime.handle_command(
        LockEdgeCommand(
            command_id="cmd-lock-topology-003",
            command_type=CommandType.LOCK_EDGE,
            payload=LockEdgePayload(edge_id=edge_id),
        )
    )

    edge = runtime.session_graph.get_edge(edge_id)
    assert edge is not None
    assert edge.locked is True
    assert edge.protected_reason is not None
    assert result.state_version == 2


def test_unlock_edge_command_requires_edge_id_and_clears_the_graph_edge() -> None:
    """Unlock commands must validate payloads and clear the target edge lock."""

    with pytest.raises(ValidationError):
        TypeAdapter(CommandEnvelope).validate_python(
            {
                "command_id": "cmd-unlock-topology-001",
                "command_type": "unlock_edge",
                "payload": {},
            }
        )

    with pytest.raises(ValidationError):
        TypeAdapter(CommandEnvelope).validate_python(
            {
                "command_id": "cmd-unlock-topology-002",
                "command_type": "unlock_edge",
                "payload": {"edge_id": "edge-1", "extra": True},
            }
        )

    runtime = _runtime()
    session_id = _start_runtime(runtime)
    edge_id = _seed_edge_id(session_id)
    runtime.session_graph.lock_edge(edge_id)

    result = runtime.handle_command(
        UnlockEdgeCommand(
            command_id="cmd-unlock-topology-003",
            command_type=CommandType.UNLOCK_EDGE,
            payload=UnlockEdgePayload(edge_id=edge_id),
        )
    )

    edge = runtime.session_graph.get_edge(edge_id)
    assert edge is not None
    assert edge.locked is False
    assert edge.protected_reason is None
    assert result.state_version == 2


def test_fork_session_command_rejects_extra_payload_fields_and_returns_new_session_id() -> (
    None
):
    """Fork commands must validate payloads and return a fresh fork session id."""

    with pytest.raises(ValidationError):
        TypeAdapter(CommandEnvelope).validate_python(
            {
                "command_id": "cmd-fork-topology-001",
                "command_type": "fork_session",
                "payload": {"fork_label": "branch-a", "extra": True},
            }
        )

    runtime = _runtime()
    source_session_id = _start_runtime(runtime)

    result = runtime.handle_command(
        ForkSessionCommand(
            command_id="cmd-fork-topology-002",
            session_id=source_session_id,
            command_type=CommandType.FORK_SESSION,
            payload=ForkSessionPayload(fork_label="branch-a"),
        )
    )

    known_session_ids = runtime.available_session_ids()
    assert result.session_id is not None
    assert result.session_id != source_session_id
    assert result.session_id in known_session_ids
    assert source_session_id in known_session_ids
    assert runtime.session_id == source_session_id
