"""Tests for export artifact builders and atomic file writing."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from graph.session_graph import SessionGraph
from models.common import (
    BudgetTelemetry,
    CheckStatus,
    CoherenceSnapshot,
    NodeCoherenceScore,
    NodeKind,
    RelationType,
    SessionStatus,
    TerminationVoteState,
)
from models.events import EventType, SessionEvent
from models.graph import GraphEdge, GraphNode
from models.session import SessionSnapshot
from runtime.exporter import build_export_artifact, write_export_artifact


def _build_session_snapshot() -> SessionSnapshot:
    now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)
    session_id = uuid4()
    return SessionSnapshot(
        session_id=session_id,
        status=SessionStatus.RUNNING,
        seed_text="A brass archive hums awake.",
        graph_version=4,
        active_node_ids=["seed", "scene-1"],
        created_at=now,
        updated_at=now,
        captured_at=now,
        coherence=CoherenceSnapshot(
            global_score=0.83,
            local_scores=[
                NodeCoherenceScore(
                    node_id="scene-1",
                    score=0.83,
                    sampled_at=now,
                )
            ],
            global_check_status=CheckStatus.PASS,
            sampled_at=now,
            checked_by="test-suite",
        ),
        budget=BudgetTelemetry(
            estimated_cost_usd=Decimal("1.25"),
            token_input_count=100,
            token_output_count=50,
            model_call_count=3,
        ),
        termination=TerminationVoteState(
            active_node_count=2,
            votes_for_termination=1,
            votes_against_termination=1,
            majority_threshold=0.75,
        ),
    )


def _build_graph(session_id: UUID) -> SessionGraph:
    session_graph = SessionGraph()
    session_graph.add_node(
        GraphNode(
            node_id="seed",
            session_id=session_id,
            node_kind=NodeKind.SEED,
            text="A brass archive hums awake.",
        )
    )
    session_graph.add_node(
        GraphNode(
            node_id="scene-1",
            session_id=session_id,
            node_kind=NodeKind.SCENE,
            text="A caretaker unlocks the first vault.",
        )
    )
    session_graph.add_edge(
        GraphEdge(
            edge_id="seed->scene-1",
            session_id=session_id,
            source_node_id="seed",
            target_node_id="scene-1",
            relation_type=RelationType.FOLLOWS,
        )
    )
    return session_graph


def _build_events(session_id: UUID) -> list[SessionEvent]:
    now = datetime(2026, 4, 7, 12, 5, tzinfo=timezone.utc)
    return [
        SessionEvent(
            event_id="evt-001",
            sequence=1,
            session_id=session_id,
            event_type=EventType.SESSION_STARTED,
            occurred_at=now,
            message="session started",
        ),
        SessionEvent(
            event_id="evt-002",
            sequence=2,
            session_id=session_id,
            event_type=EventType.COHERENCE_SAMPLED,
            occurred_at=now,
            message="coherence sampled",
            actor_id="mutation-engine",
            target_ids=["scene-1"],
        ),
    ]


def test_build_export_artifact_populates_all_contract_blocks() -> None:
    """Export builders should assemble the frozen contract payload."""

    session = _build_session_snapshot()
    session_graph = _build_graph(session.session_id)
    events = _build_events(session.session_id)
    exported_at = datetime(2026, 4, 7, 12, 30, tzinfo=timezone.utc)

    artifact = build_export_artifact(
        session_snapshot=session,
        session_graph=session_graph,
        events=events,
        exported_at=exported_at,
    )

    assert artifact.schema_version == "1.0.0"
    assert artifact.exported_at == exported_at
    assert artifact.session.session_id == session.session_id
    assert artifact.session.final_coherence_score == pytest.approx(0.83)
    assert artifact.session.estimated_cost_usd == Decimal("1.25")
    assert artifact.graph.node_count == 2
    assert artifact.graph.edge_count == 1
    assert len(artifact.graph.nodes) == 2
    assert len(artifact.graph.edges) == 1
    assert artifact.events == events
    assert artifact.summary.total_events == 2
    assert artifact.summary.terminated_due_to_votes is False


def test_write_export_artifact_rejects_directory_output_path(tmp_path: Path) -> None:
    """Atomic writer should reject paths that point to a directory."""

    session = _build_session_snapshot()
    session_graph = _build_graph(session.session_id)
    artifact = build_export_artifact(
        session_snapshot=session,
        session_graph=session_graph,
        events=_build_events(session.session_id),
    )

    output_path = tmp_path / "exports"
    output_path.mkdir()

    with pytest.raises(ValueError, match="path"):
        write_export_artifact(output_path, artifact)


def test_write_export_artifact_writes_complete_json(tmp_path: Path) -> None:
    """Atomic writer should persist a complete JSON artifact."""

    session = _build_session_snapshot()
    session_graph = _build_graph(session.session_id)
    artifact = build_export_artifact(
        session_snapshot=session,
        session_graph=session_graph,
        events=_build_events(session.session_id),
    )

    output_path = tmp_path / "exports" / "session-export.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written_path = write_export_artifact(output_path, artifact)

    assert written_path == output_path
    assert output_path.exists()
    assert output_path.read_text().startswith("{")
