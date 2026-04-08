"""Request models for graph lifecycle operations."""

from __future__ import annotations

from pydantic import ConfigDict, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["GraphForkRequest"]

_ForkEdgeId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_ForkLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class GraphForkRequest(StrictBaseModel):
    """Request payload to fork a source graph at a specific edge."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_graph_id: str = Field(alias="sourceGraphId", min_length=1)
    fork_edge_id: _ForkEdgeId = Field(alias="forkEdgeId")
    custom_seed: _SeedText | None = Field(default=None, alias="customSeed")
    label: _ForkLabel | None = None

    @field_validator("source_graph_id")
    @classmethod
    def _validate_source_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="source_graph_id")
