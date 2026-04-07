"""Integration tests for the export-session command flow."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandType,
    ExportSessionCommand,
    ExportSessionPayload,
    StartSessionCommand,
    StartSessionPayload,
)
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider

pytestmark = pytest.mark.integration


def _build_runtime() -> SessionRuntime:
    """Build a runtime with deterministic scene generation."""

    return SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )


def _start_session(runtime: SessionRuntime) -> UUID:
    """Start a session and return the active session identifier."""

    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-export-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass archive hums awake."),
        )
    )

    assert start_result.accepted is True
    assert start_result.session_id is not None
    return start_result.session_id


def test_export_session_rejects_directory_output_path(tmp_path: Path) -> None:
    """Export should reject an output path that points to a directory."""

    runtime = _build_runtime()
    session_id = _start_session(runtime)

    output_path = tmp_path / "exports"
    output_path.mkdir()

    result = runtime.handle_command(
        ExportSessionCommand(
            command_id="cmd-export-directory-001",
            command_type=CommandType.EXPORT_SESSION,
            session_id=session_id,
            payload=ExportSessionPayload(output_path=str(output_path)),
        )
    )

    assert result.accepted is False
    assert "path" in result.message.lower()


def test_export_session_rejects_non_writable_output_path(tmp_path: Path) -> None:
    """Export should reject output paths that cannot be written."""

    runtime = _build_runtime()
    session_id = _start_session(runtime)

    read_only_dir = tmp_path / "read-only"
    read_only_dir.mkdir()
    read_only_dir.chmod(0o555)
    output_path = read_only_dir / "session-export.json"

    try:
        result = runtime.handle_command(
            ExportSessionCommand(
                command_id="cmd-export-readonly-001",
                command_type=CommandType.EXPORT_SESSION,
                session_id=session_id,
                payload=ExportSessionPayload(output_path=str(output_path)),
            )
        )
    finally:
        read_only_dir.chmod(0o755)

    assert result.accepted is False
    assert "writable" in result.message.lower()


def test_export_session_writes_complete_artifact(tmp_path: Path) -> None:
    """Export should write the session, graph, events, and summary blocks."""

    runtime = _build_runtime()
    session_id = _start_session(runtime)

    output_path = tmp_path / "exports" / "session-export.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = runtime.handle_command(
        ExportSessionCommand(
            command_id="cmd-export-success-001",
            command_type=CommandType.EXPORT_SESSION,
            session_id=session_id,
            payload=ExportSessionPayload(output_path=str(output_path)),
        )
    )

    assert result.accepted is True
    assert output_path.exists()

    artifact = json.loads(output_path.read_text())
    assert {"session", "graph", "events", "summary"}.issubset(artifact)
    assert artifact["session"] is not None
    assert artifact["graph"] is not None
    assert artifact["events"] is not None
    assert artifact["summary"] is not None
