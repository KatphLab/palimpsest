"""Graph session model for tracking individual graph state in multi-graph runtime."""

from __future__ import annotations

from pydantic import Field, field_validator

from models.common import StrictBaseModel, UTCDateTime
from models.execution import ExecutionStatus
from utils.time import utc_now
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["GraphSession"]


class GraphSession(StrictBaseModel):
    """Represents one independently progressing narrative graph.

    Tracks the graph's identity, execution state, focus status, and current node
    for fork/navigation actions in the multi-graph TUI.
    """

    graph_id: str = Field(min_length=1, description="Stable graph identifier (UUID)")
    current_node_id: str | None = Field(
        default=None,
        min_length=1,
        description="Current focused node for fork/navigation actions",
    )
    execution_status: ExecutionStatus = Field(
        default=ExecutionStatus.IDLE,
        description="Runtime execution state",
    )
    is_active: bool = Field(
        default=False,
        description="Whether this graph is currently focused in TUI",
    )
    last_activity_at: UTCDateTime = Field(
        default_factory=utc_now,
        description="Last progression/update timestamp",
    )

    @field_validator("graph_id")
    @classmethod
    def _validate_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="graph_id")

    @field_validator("current_node_id")
    @classmethod
    def _validate_current_node_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if len(value.strip()) < 1:
            raise ValueError("current_node_id must be non-empty when provided")

        return value
