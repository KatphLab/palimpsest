"""Export artifact models for frozen session snapshots."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from models.common import (
    DriftCategory,
    ProtectionReason,
    SessionStatus,
    StrictBaseModel,
    UTCDateTime,
)
from models.events import EventRecord

__all__ = [
    "ExportArtifact",
    "ExportEdge",
    "ExportGraph",
    "ExportNode",
    "ExportSessionSnapshot",
    "ExportSessionSummary",
]

_LabelText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExportNode(StrictBaseModel):
    """Serialized node record for offline export."""

    node_id: str = Field(min_length=1)
    label: _LabelText
    text: _LabelText
    entropy_score: float = Field(ge=0.0, le=1.0)
    drift_category: DriftCategory
    is_seed_protected: bool


class ExportEdge(StrictBaseModel):
    """Serialized edge record for offline export."""

    edge_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    relation_type: str = Field(min_length=1)
    locked: bool
    protected_reason: ProtectionReason | None = None


class ExportGraph(StrictBaseModel):
    """Serialized graph block for export artifacts."""

    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    nodes: list[ExportNode]
    edges: list[ExportEdge]

    @model_validator(mode="after")
    def _sync_counts(self) -> ExportGraph:
        if self.node_count != len(self.nodes):
            raise ValueError("node_count must match the number of exported nodes")

        if self.edge_count != len(self.edges):
            raise ValueError("edge_count must match the number of exported edges")

        return self


class ExportSessionSnapshot(StrictBaseModel):
    """Frozen session metadata included in an export artifact."""

    session_id: UUID
    status: SessionStatus
    seed_text: _LabelText
    parent_session_id: UUID | None = None
    graph_version: int = Field(ge=0)
    final_coherence_score: float = Field(ge=0.0, le=1.0)
    estimated_cost_usd: Decimal = Field(ge=0)


class ExportSessionSummary(StrictBaseModel):
    """Human-readable export summary block."""

    status: SessionStatus
    final_coherence_score: float = Field(ge=0.0, le=1.0)
    estimated_cost_usd: Decimal = Field(ge=0)
    total_events: int = Field(ge=0)
    terminated_due_to_votes: bool


class ExportArtifact(StrictBaseModel):
    """Schema-versioned export artifact document."""

    schema_version: str = Field(default="1.0.0", min_length=1)
    exported_at: UTCDateTime
    session: ExportSessionSnapshot
    graph: ExportGraph
    events: list[EventRecord]
    summary: ExportSessionSummary

    @model_validator(mode="after")
    def _validate_event_session_ids(self) -> ExportArtifact:
        if self.events:
            session_id = str(self.session.session_id)
            for event in self.events:
                event_session_id = str(event.session_id)
                if event_session_id != session_id:
                    raise ValueError(
                        "export events must belong to the exported session"
                    )

            expected_sequence = 1
            for event in self.events:
                if event.sequence != expected_sequence:
                    raise ValueError(
                        "export events must retain a contiguous chronological sequence"
                    )
                expected_sequence += 1

        return self
