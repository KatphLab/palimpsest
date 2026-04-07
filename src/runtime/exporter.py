"""Export artifact builders and atomic file persistence."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from graph.session_graph import SessionGraph
from models.common import DriftCategory, NodeKind
from models.events import EventRecord
from models.export import (
    ExportArtifact,
    ExportEdge,
    ExportGraph,
    ExportNode,
    ExportSessionSnapshot,
    ExportSessionSummary,
)
from models.graph import GraphEdge, GraphNode
from models.node import SceneNode
from models.session import SessionSnapshot

__all__ = [
    "build_export_artifact",
    "build_export_edge",
    "build_export_graph",
    "build_export_node",
    "build_export_session_snapshot",
    "build_export_summary",
    "write_export_artifact",
]

LOGGER = logging.getLogger(__name__)


def build_export_node(
    graph_node: GraphNode, scene_node: SceneNode | None = None
) -> ExportNode:
    """Build an export node record from graph and scene metadata."""

    if scene_node is None:
        entropy_score = 0.0
        drift_category = DriftCategory.STABLE
        is_seed_protected = graph_node.node_kind is NodeKind.SEED
    else:
        entropy_score = scene_node.entropy_score
        drift_category = scene_node.drift_category or DriftCategory.STABLE
        is_seed_protected = scene_node.is_seed_protected

    return ExportNode(
        node_id=graph_node.node_id,
        label=graph_node.node_kind.value,
        text=graph_node.text,
        entropy_score=entropy_score,
        drift_category=drift_category,
        is_seed_protected=is_seed_protected,
    )


def build_export_edge(edge: GraphEdge) -> ExportEdge:
    """Build an export edge record from a graph edge."""

    return ExportEdge(
        edge_id=edge.edge_id,
        source_node_id=edge.source_node_id,
        target_node_id=edge.target_node_id,
        relation_type=edge.relation_type.value,
        locked=edge.locked,
        protected_reason=edge.protected_reason,
    )


def build_export_graph(session_graph: SessionGraph, session_id: UUID) -> ExportGraph:
    """Build the graph block for an export artifact."""

    nodes: list[ExportNode] = []
    for node_id in sorted(session_graph.graph.nodes):
        node_data = session_graph.graph.nodes[node_id]
        graph_node = node_data.get("node")
        if not isinstance(graph_node, GraphNode):
            continue

        if graph_node.session_id != session_id:
            continue

        scene_node = node_data.get("scene_node")
        if scene_node is not None and not isinstance(scene_node, SceneNode):
            scene_node = None

        nodes.append(build_export_node(graph_node, scene_node))

    edges: list[ExportEdge] = []
    for source_node_id, target_node_id, edge_id, edge_data in sorted(
        session_graph.graph.edges(keys=True, data=True), key=lambda item: str(item[2])
    ):
        edge = edge_data.get("edge")
        if not isinstance(edge, GraphEdge):
            continue

        if edge.session_id != session_id:
            continue

        edges.append(build_export_edge(edge))

    if not any(node.label == NodeKind.SEED.value for node in nodes):
        raise ValueError("seed node is required for export artifacts")

    return ExportGraph(
        node_count=len(nodes),
        edge_count=len(edges),
        nodes=nodes,
        edges=edges,
    )


def _extract_snapshot_metrics(
    session_snapshot: SessionSnapshot,
) -> tuple[float, Decimal]:
    """Extract coherence score and estimated cost from session snapshot."""

    final_coherence_score = 0.0
    if session_snapshot.coherence is not None:
        final_coherence_score = session_snapshot.coherence.global_score

    estimated_cost_usd = Decimal("0")
    if session_snapshot.budget is not None:
        estimated_cost_usd = session_snapshot.budget.estimated_cost_usd

    return final_coherence_score, estimated_cost_usd


def build_export_session_snapshot(
    session_snapshot: SessionSnapshot,
) -> ExportSessionSnapshot:
    """Build the frozen session block for an export artifact."""

    final_coherence_score, estimated_cost_usd = _extract_snapshot_metrics(
        session_snapshot
    )

    return ExportSessionSnapshot(
        session_id=session_snapshot.session_id,
        status=session_snapshot.status,
        seed_text=session_snapshot.seed_text,
        parent_session_id=session_snapshot.parent_session_id,
        graph_version=session_snapshot.graph_version,
        final_coherence_score=final_coherence_score,
        estimated_cost_usd=estimated_cost_usd,
    )


def build_export_summary(
    session_snapshot: SessionSnapshot,
    *,
    total_events: int,
) -> ExportSessionSummary:
    """Build the human-readable summary block for an export artifact."""

    final_coherence_score, estimated_cost_usd = _extract_snapshot_metrics(
        session_snapshot
    )

    terminated_due_to_votes = False
    if session_snapshot.termination is not None:
        terminated_due_to_votes = session_snapshot.termination.termination_reached

    return ExportSessionSummary(
        status=session_snapshot.status,
        final_coherence_score=final_coherence_score,
        estimated_cost_usd=estimated_cost_usd,
        total_events=total_events,
        terminated_due_to_votes=terminated_due_to_votes,
    )


def build_export_artifact(
    session_snapshot: SessionSnapshot,
    session_graph: SessionGraph,
    events: Sequence[EventRecord],
    exported_at: datetime | None = None,
) -> ExportArtifact:
    """Build a complete export artifact from a frozen session snapshot."""

    exported_at = exported_at or datetime.now(timezone.utc)
    ordered_events = sorted(events, key=lambda event: event.sequence)
    export_session = build_export_session_snapshot(session_snapshot)
    export_graph = build_export_graph(
        session_graph, session_id=session_snapshot.session_id
    )
    export_summary = build_export_summary(
        session_snapshot,
        total_events=len(ordered_events),
    )

    return ExportArtifact(
        exported_at=exported_at,
        session=export_session,
        graph=export_graph,
        events=ordered_events,
        summary=export_summary,
    )


def write_export_artifact(output_path: str | Path, artifact: ExportArtifact) -> Path:
    """Write an export artifact atomically to disk."""

    target_path = Path(output_path)
    _validate_output_path(target_path)

    payload = artifact.model_dump(mode="json", exclude_none=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    temp_path: Path | None = None
    replaced = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target_path.parent,
            prefix=f".{target_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)

        os.replace(temp_path, target_path)
        replaced = True
        _fsync_directory(target_path.parent)
        LOGGER.info("wrote export artifact to %s", target_path)
        return target_path
    finally:
        if temp_path is not None and not replaced:
            temp_path.unlink(missing_ok=True)


def _validate_output_path(output_path: Path) -> None:
    """Validate that an export target path is writable and file-shaped."""

    if output_path.exists() and output_path.is_dir():
        raise ValueError("output path must reference a file, not a directory")

    parent = output_path.parent
    if not parent.exists():
        raise ValueError("output path parent directory does not exist")

    if not parent.is_dir():
        raise ValueError("output path parent must be a directory")

    if not os.access(parent, os.W_OK | os.X_OK):
        raise ValueError("output path parent is not writable")


def _fsync_directory(directory: Path) -> None:
    """Flush directory metadata so the atomic replace is durable."""

    dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
