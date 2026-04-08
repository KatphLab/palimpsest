"""Response models for graph lifecycle operations."""

from __future__ import annotations

from pydantic import ConfigDict, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel, UTCDateTime
from models.multi_graph_view import GraphSummary
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["EdgeReference", "GraphForkResponse"]

_EdgeIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_NodeIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class EdgeReference(StrictBaseModel):
    """Reference to the edge where a fork was created."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    edge_id: _EdgeIdentifier = Field(alias="edgeId")
    source_node_id: _NodeIdentifier = Field(alias="sourceNodeId")
    target_node_id: _NodeIdentifier = Field(alias="targetNodeId")


class GraphForkResponse(StrictBaseModel):
    """Result payload returned after a successful graph fork operation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    forked_graph_id: str = Field(alias="forkedGraphId", min_length=1)
    fork_point: EdgeReference = Field(alias="forkPoint")
    seed: _SeedText
    creation_time: UTCDateTime = Field(alias="creationTime")
    parent_graph_id: str = Field(alias="parentGraphId", min_length=1)
    graph_summary: GraphSummary = Field(alias="graphSummary")

    @field_validator("forked_graph_id")
    @classmethod
    def _validate_forked_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="forked_graph_id")

    @field_validator("parent_graph_id")
    @classmethod
    def _validate_parent_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="parent_graph_id")
