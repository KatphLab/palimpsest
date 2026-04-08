"""Graph topology models for typed nodes and edges."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from models.common import (
    NodeKind,
    ProtectionReason,
    RelationType,
    StrictBaseModel,
    UTCDateTime,
)
from utils.time import utc_now

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
    created_at: UTCDateTime = Field(default_factory=utc_now)
    updated_at: UTCDateTime = Field(default_factory=utc_now)
    locked: bool = False
    protected_reason: ProtectionReason | None = None
