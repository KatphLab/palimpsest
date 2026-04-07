"""Integration tests for locked-edge protection."""

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandType,
    EmptyPayload,
    LockEdgeCommand,
    LockEdgePayload,
    PauseSessionCommand,
    ResumeSessionCommand,
    StartSessionCommand,
    StartSessionPayload,
)
from models.common import ProtectionReason
from models.graph import GraphEdge
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime

pytestmark = pytest.mark.integration


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for lock-protection tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


def _single_edge(runtime: SessionRuntime) -> GraphEdge:
    """Return the only edge produced during session bootstrap."""

    edge_rows = list(runtime.session_graph.graph.edges(keys=True, data=True))
    assert len(edge_rows) == 1

    _, _, _, edge_data = edge_rows[0]
    edge = edge_data["edge"]
    assert isinstance(edge, GraphEdge)
    return edge


def test_locked_edge_survives_mutation_cycle_attempt() -> None:
    """A locked edge should resist removal attempts across a mutation cycle."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    start_command = StartSessionCommand(
        command_id="cmd-start-lock-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A clockwork bird pauses mid-song."),
    )

    start_result = runtime.handle_command(start_command)
    edge = _single_edge(runtime)
    lock_command = LockEdgeCommand(
        command_id="cmd-lock-edge-001",
        command_type=CommandType.LOCK_EDGE,
        session_id=start_result.session_id,
        payload=LockEdgePayload(edge_id=edge.edge_id),
    )

    lock_result = runtime.handle_command(lock_command)

    assert start_result.accepted is True
    assert start_result.session_id is not None
    assert lock_result.accepted is True

    pause_result = runtime.handle_command(
        PauseSessionCommand(
            command_id="cmd-pause-lock-001",
            command_type=CommandType.PAUSE_SESSION,
            payload=EmptyPayload(),
        )
    )
    resume_result = runtime.handle_command(
        ResumeSessionCommand(
            command_id="cmd-resume-lock-001",
            command_type=CommandType.RESUME_SESSION,
            payload=EmptyPayload(),
        )
    )

    with pytest.raises(ValueError):
        runtime.session_graph.remove_edge(edge.edge_id)

    surviving_edge = runtime.session_graph.get_edge(edge.edge_id)
    assert pause_result.accepted is True
    assert resume_result.accepted is True
    assert surviving_edge is not None
    assert surviving_edge.locked is True
    assert surviving_edge.protected_reason is ProtectionReason.USER_LOCK
