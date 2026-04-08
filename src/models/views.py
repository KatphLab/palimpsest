"""Models for multi-graph view preferences, filters, and payloads."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel, UTCDateTime
from models.multi_graph_view import GraphSummary
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["FilterState", "MultiGraphView", "ViewPreferences"]

_SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]

ViewSortField = Literal["createdAt", "name", "nodeCount", "lastModified"]
ViewSortOrder = Literal["asc", "desc"]
ViewDisplayMode = Literal["list", "grid", "tree"]
GraphStatusFilter = Literal["active", "archived"]


class ViewPreferences(StrictBaseModel):
    """User preferences for sorting and rendering multi-graph results."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sort_by: ViewSortField = Field(default="createdAt", alias="sortBy")
    sort_order: ViewSortOrder = Field(default="desc", alias="sortOrder")
    display_mode: ViewDisplayMode = Field(default="list", alias="displayMode")


class FilterState(StrictBaseModel):
    """Active filter criteria for querying graph summaries."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    search_query: _SearchQuery | None = Field(default=None, alias="searchQuery")
    fork_source: str | None = Field(default=None, alias="forkSource")
    created_after: UTCDateTime | None = Field(default=None, alias="createdAfter")
    created_before: UTCDateTime | None = Field(default=None, alias="createdBefore")
    status: GraphStatusFilter | None = None

    @field_validator("fork_source")
    @classmethod
    def _validate_fork_source(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return ensure_valid_uuid(value, field_name="fork_source")


class MultiGraphView(StrictBaseModel):
    """Complete state payload for the multi-graph browser view."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    graphs: list[GraphSummary] = Field(max_length=1000)
    active_graph_id: str | None = Field(default=None, alias="activeGraphId")
    total_count: int = Field(alias="totalCount", ge=0)
    filters: FilterState = Field(default_factory=FilterState)
    view_prefs: ViewPreferences = Field(
        default_factory=ViewPreferences,
        alias="viewPrefs",
    )

    @field_validator("active_graph_id")
    @classmethod
    def _validate_active_graph_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return ensure_valid_uuid(value, field_name="active_graph_id")
