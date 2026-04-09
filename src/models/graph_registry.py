"""Graph registry model for ordered runtime collection of available graphs."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from models.common import StrictBaseModel
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["GraphRegistry"]


class GraphRegistry(StrictBaseModel):
    """Ordered runtime collection of available graphs and active index.

    Used for graph cycling navigation with Tab/Shift+Tab keybindings.
    Navigation rules:
        - Tab computes: (active_index + 1) % total_graphs
        - Shift+Tab computes: (active_index - 1) % total_graphs
    """

    graph_ids: list[str] = Field(
        default_factory=list,
        description="Ordered graph IDs for cycle navigation (UUIDs)",
    )
    active_index: int = Field(
        default=0,
        ge=0,
        description="Zero-based index in graph_ids for the active graph",
    )

    @field_validator("graph_ids")
    @classmethod
    def _validate_graph_ids(cls, value: list[str]) -> list[str]:
        """Validate all graph IDs are valid UUIDs."""
        for graph_id in value:
            ensure_valid_uuid(graph_id, field_name="graph_ids")

        return value

    @model_validator(mode="after")
    def _validate_active_index_bounds(self) -> GraphRegistry:
        """Ensure active_index is within valid bounds when graphs exist."""
        total_graphs = len(self.graph_ids)

        if total_graphs > 0 and self.active_index >= total_graphs:
            raise ValueError(
                f"active_index ({self.active_index}) must be less than "
                f"total_graphs ({total_graphs})"
            )

        return self

    @property
    def total_graphs(self) -> int:
        """Return the count of tracked graphs."""
        return len(self.graph_ids)

    @property
    def active_graph_id(self) -> str | None:
        """Return the currently active graph ID, or None if no graphs."""
        if not self.graph_ids:
            return None

        return self.graph_ids[self.active_index]
