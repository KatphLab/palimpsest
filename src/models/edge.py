"""Narrative edge models for typed topology control."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints, model_validator

from models.common import ProtectionReason, RelationType, StrictBaseModel

__all__ = ["NarrativeEdge"]

_EdgeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_NodeId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_RelationGroupId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
_ProvenanceEventId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class NarrativeEdge(StrictBaseModel):
    """Typed narrative edge with lock and protection invariants."""

    edge_id: _EdgeId
    source_node_id: _NodeId
    target_node_id: _NodeId
    relation_type: RelationType
    relation_group_id: _RelationGroupId
    provenance_event_id: _ProvenanceEventId
    locked: bool = False
    protected_reason: ProtectionReason | None = None

    @model_validator(mode="after")
    def _validate_lock_protection_state(self) -> NarrativeEdge:
        if self.protected_reason is ProtectionReason.USER_LOCK:
            self.locked = True

        if self.locked and self.protected_reason is None:
            raise ValueError("locked edges require a protected reason")

        return self
