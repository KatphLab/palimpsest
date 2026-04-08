"""Contract tests for deterministic runtime command rejections."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandType,
    ExportSessionCommand,
    ExportSessionPayload,
    InspectNodeCommand,
    InspectNodePayload,
    LockEdgeCommand,
    LockEdgePayload,
    StartSessionCommand,
    StartSessionPayload,
    UnlockEdgeCommand,
    UnlockEdgePayload,
)
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider

pytestmark = pytest.mark.contracts


def _build_runtime() -> SessionRuntime:
    """Build a runtime with deterministic scene generation."""

    return SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )


def _start_session(runtime: SessionRuntime) -> UUID:
    """Start a session and return the active session identifier."""

    result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-runtime-rejections-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A deterministic seed."),
        )
    )
    assert result.accepted is True
    assert result.session_id is not None
    return result.session_id


def _seed_edge_id(session_id: UUID) -> str:
    """Build the deterministic bootstrap edge identifier."""

    prefix = session_id.hex[:8]
    return f"{prefix}-seed->{prefix}-scene-1"


def test_runtime_rejects_lock_edge_when_command_session_mismatches_active() -> None:
    """Lock-edge should reject mismatched session identifiers."""

    runtime = _build_runtime()
    session_id = _start_session(runtime)
    edge_id = _seed_edge_id(session_id)

    result = runtime.handle_command(
        LockEdgeCommand(
            command_id="cmd-lock-reject-001",
            command_type=CommandType.LOCK_EDGE,
            session_id=uuid4(),
            payload=LockEdgePayload(edge_id=edge_id),
        )
    )

    assert result.accepted is False
    assert result.message == "command session_id must match the active session"


def test_runtime_rejects_unlock_edge_when_command_session_mismatches_active() -> None:
    """Unlock-edge should reject mismatched session identifiers."""

    runtime = _build_runtime()
    session_id = _start_session(runtime)
    edge_id = _seed_edge_id(session_id)

    result = runtime.handle_command(
        UnlockEdgeCommand(
            command_id="cmd-unlock-reject-001",
            command_type=CommandType.UNLOCK_EDGE,
            session_id=uuid4(),
            payload=UnlockEdgePayload(edge_id=edge_id),
        )
    )

    assert result.accepted is False
    assert result.message == "command session_id must match the active session"


def test_runtime_rejects_inspect_node_when_command_session_mismatches_active() -> None:
    """Inspect-node should reject mismatched session identifiers."""

    runtime = _build_runtime()
    _start_session(runtime)
    assert runtime.session is not None
    node_id = runtime.session.active_node_ids[-1]

    result = runtime.handle_command(
        InspectNodeCommand(
            command_id="cmd-inspect-reject-001",
            command_type=CommandType.INSPECT_NODE,
            session_id=uuid4(),
            payload=InspectNodePayload(node_id=node_id),
        )
    )

    assert result.accepted is False
    assert result.message == "command session_id must match the active session"


def test_runtime_rejects_export_session_when_command_session_mismatches_active(
    tmp_path: Path,
) -> None:
    """Export-session should reject mismatched session identifiers."""

    runtime = _build_runtime()
    _start_session(runtime)
    output_path = tmp_path / "session-export.json"

    result = runtime.handle_command(
        ExportSessionCommand(
            command_id="cmd-export-reject-001",
            command_type=CommandType.EXPORT_SESSION,
            session_id=uuid4(),
            payload=ExportSessionPayload(output_path=str(output_path)),
        )
    )

    assert result.accepted is False
    assert result.message == "command session_id must match the active session"


def test_runtime_rejects_export_when_active_session_state_is_unresolved(
    tmp_path: Path,
) -> None:
    """Export should reject when runtime cannot resolve the active session state."""

    runtime = _build_runtime()
    session_id = _start_session(runtime)
    output_path = tmp_path / "session-export.json"
    runtime._session_states.pop(session_id)

    result = runtime.handle_command(
        ExportSessionCommand(
            command_id="cmd-export-reject-002",
            command_type=CommandType.EXPORT_SESSION,
            session_id=session_id,
            payload=ExportSessionPayload(output_path=str(output_path)),
        )
    )

    assert result.accepted is False
    assert result.message == "active session state is unavailable"
