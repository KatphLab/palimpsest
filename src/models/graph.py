"""Graph topology models for typed nodes and edges."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import Field

from models.common import (
    NodeKind,
    ProtectionReason,
    RelationType,
    StrictBaseModel,
    UTCDateTime,
)

__all__ = ["GraphEdge", "GraphNode"]


class GraphNode(StrictBaseModel):
    """Typed node record stored in the session graph."""

    node_id: str = Field(min_length=1)
    session_id: UUID
    node_kind: NodeKind
    text: str = Field(min_length=1)


class GraphEdge(StrictBaseModel):
    """Typed edge record stored in the session graph."""

    edge_id: str = Field(min_length=1)
    session_id: UUID
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    relation_type: RelationType
    created_at: UTCDateTime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: UTCDateTime = Field(default_factory=lambda: datetime.now(timezone.utc))
    locked: bool = False
    protected_reason: ProtectionReason | None = None
