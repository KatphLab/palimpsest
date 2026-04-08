"""Graph instance model with fork metadata and graph payload."""

from __future__ import annotations

from enum import StrEnum

import networkx as nx
from pydantic import ConfigDict, Field, JsonValue, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel, UTCDateTime
from models.fork_point import ForkPoint
from models.multi_graph_view import GraphSummary
from models.seed_config import SeedConfiguration
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["GraphInstance", "GraphLifecycleState"]

_GraphName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class GraphLifecycleState(StrEnum):
    """Lifecycle state for a graph instance."""

    CREATED = "created"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class GraphInstance(StrictBaseModel):
    """Complete isolated graph state persisted for each branch."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    id: str = Field(min_length=1)
    name: _GraphName
    created_at: UTCDateTime
    fork_point: ForkPoint | None = None
    seed_config: SeedConfiguration
    graph_data: nx.DiGraph  # type: ignore[type-arg]  # NetworkX runtime type is not subscriptable.
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    last_modified: UTCDateTime
    state: GraphLifecycleState = GraphLifecycleState.CREATED

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="id")

    @field_validator("graph_data")
    @classmethod
    def _validate_graph_data(
        cls,
        value: nx.DiGraph,  # type: ignore[type-arg]  # NetworkX runtime type is not subscriptable.
    ) -> nx.DiGraph:  # type: ignore[type-arg]  # NetworkX runtime type is not subscriptable.
        if not isinstance(value, nx.DiGraph):
            raise TypeError("graph_data must be a networkx.DiGraph")

        return value

    def to_summary(self) -> GraphSummary:
        """Create a summary projection used by multi-graph list views."""

        return GraphSummary(
            id=self.id,
            name=self.name,
            node_count=self.graph_data.number_of_nodes(),
            edge_count=self.graph_data.number_of_edges(),
            created_at=self.created_at,
            fork_source=self.fork_point.source_graph_id if self.fork_point else None,
            current_state=self.state.value,
            last_modified=self.last_modified,
            labels=[],
        )
