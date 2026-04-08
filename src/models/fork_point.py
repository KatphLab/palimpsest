"""Fork metadata model for graph forking operations."""

from __future__ import annotations

from pydantic import ConfigDict, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel, UTCDateTime
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["ForkPoint"]

_ForkEdgeId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_ForkLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class ForkPoint(StrictBaseModel):
    """Location and metadata describing where a graph was forked."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_graph_id: str = Field(min_length=1)
    fork_edge_id: _ForkEdgeId
    timestamp: UTCDateTime
    label: _ForkLabel | None = None

    @field_validator("source_graph_id")
    @classmethod
    def _validate_source_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="source_graph_id")
