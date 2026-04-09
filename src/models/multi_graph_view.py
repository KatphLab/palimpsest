"""Models for multi-graph list and browsing views."""

from __future__ import annotations

from pydantic import Field, StringConstraints, ValidationInfo, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel, UTCDateTime
from utils.uuid_validation import ensure_valid_uuid

__all__ = [
    "GraphListView",
    "GraphPosition",
    "GraphSummary",
    "MultiGraphViewState",
]

_GraphName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
_CurrentState = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class GraphSummary(StrictBaseModel):
    """Lightweight metadata representation for a graph instance."""

    id: str = Field(min_length=1)
    name: _GraphName
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    created_at: UTCDateTime
    fork_source: str | None = None
    current_state: _CurrentState
    last_modified: UTCDateTime
    seed: _SeedText | None = None
    labels: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="id")

    @field_validator("fork_source")
    @classmethod
    def _validate_fork_source(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return ensure_valid_uuid(value, field_name="fork_source")


class GraphPosition(StrictBaseModel):
    """Position information for a graph in the multi-graph registry."""

    graph_id: str = Field(min_length=1, description="Graph identifier (UUID)")
    position: int = Field(
        ge=1,
        description="1-based position in the graph list",
    )
    is_active: bool = Field(
        default=False,
        description="Whether this graph is currently active",
    )

    @field_validator("graph_id")
    @classmethod
    def _validate_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="graph_id")


class GraphListView(StrictBaseModel):
    """Ordered list view of all graphs for display and navigation."""

    graphs: list[GraphPosition] = Field(
        default_factory=list,
        description="Ordered list of graph positions",
    )
    active_index: int = Field(
        default=0,
        ge=0,
        description="Zero-based index of the active graph",
    )
    total_count: int = Field(
        default=0,
        ge=0,
        description="Total number of graphs",
    )

    @field_validator("graphs")
    @classmethod
    def _validate_graphs(cls, value: list[GraphPosition]) -> list[GraphPosition]:
        """Validate that graph positions are sequential starting from 1."""
        if not value:
            return value

        positions = [g.position for g in value]
        expected = list(range(1, len(value) + 1))

        if sorted(positions) != expected:
            raise ValueError("graph positions must be sequential from 1 to n")

        # Validate unique graph_ids
        graph_ids = [g.graph_id for g in value]
        if len(graph_ids) != len(set(graph_ids)):
            raise ValueError("graph_ids must be unique within the list")

        return value


class MultiGraphViewState(StrictBaseModel):
    """Complete multi-graph view state for TUI rendering.

    Combines graph summaries, navigation state, and status information
    for the multi-graph TUI interface.
    """

    graph_list: GraphListView = Field(
        description="Ordered list of graph positions",
    )
    summaries: list[GraphSummary] = Field(
        default_factory=list,
        description="Detailed summaries for each graph",
    )
    active_graph_id: str | None = Field(
        default=None,
        description="Currently active graph identifier (UUID)",
    )

    @field_validator("active_graph_id")
    @classmethod
    def _validate_active_graph_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return ensure_valid_uuid(value, field_name="active_graph_id")

    @field_validator("summaries")
    @classmethod
    def _validate_summaries_match_list(
        cls,
        summaries: list[GraphSummary],
        info: ValidationInfo,
    ) -> list[GraphSummary]:
        """Validate that summaries correspond to graph list entries.

        Only validates when summaries are provided (non-empty list).
        Empty list is allowed for cases where summaries are loaded separately.
        """
        if not summaries:
            return summaries

        graph_list = info.data.get("graph_list")
        if graph_list is None:
            return summaries

        list_ids = {g.graph_id for g in graph_list.graphs}
        summary_ids = {s.id for s in summaries}

        # All list entries must have a summary
        missing = list_ids - summary_ids
        if missing:
            raise ValueError(f"missing summaries for graph_ids: {missing}")

        return summaries
