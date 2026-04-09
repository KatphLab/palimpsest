"""Response models for graph lifecycle operations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel, UTCDateTime
from models.execution import ExecutionStatus
from models.multi_graph_view import GraphSummary
from utils.uuid_validation import ensure_valid_uuid

__all__ = [
    "EdgeReference",
    "GraphForkResponse",
    "GraphSwitchResponse",
    "MultiGraphStatusSnapshot",
    "RunningState",
]

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

    edge_id: _EdgeIdentifier
    source_node_id: _NodeIdentifier
    target_node_id: _NodeIdentifier


class GraphForkResponse(StrictBaseModel):
    """Result payload returned after a successful graph fork operation."""

    forked_graph_id: str = Field(min_length=1)
    fork_point: EdgeReference
    seed: _SeedText
    creation_time: UTCDateTime
    parent_graph_id: str = Field(min_length=1)
    graph_summary: GraphSummary

    @field_validator("forked_graph_id")
    @classmethod
    def _validate_forked_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="forked_graph_id")

    @field_validator("parent_graph_id")
    @classmethod
    def _validate_parent_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="parent_graph_id")


class GraphSwitchResponse(StrictBaseModel):
    """Result payload returned after switching active graph context."""

    previous_graph_id: str | None = None
    current_graph_id: str = Field(min_length=1)
    load_time_ms: float = Field(ge=0)
    graph_summary: GraphSummary

    @field_validator("previous_graph_id")
    @classmethod
    def _validate_previous_graph_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return ensure_valid_uuid(value, field_name="previous_graph_id")

    @field_validator("current_graph_id")
    @classmethod
    def _validate_current_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="current_graph_id")


class RunningState(StrEnum):
    """Execution states for graph running status display.

    Mirrors ExecutionStatus for UI display purposes.
    """

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class MultiGraphStatusSnapshot(StrictBaseModel):
    """Multi-graph status snapshot for TUI display.

    Contract per CA-003: contains active graph position, total graph count,
    and active graph running state.
    """

    active_position: int = Field(
        ge=1,
        description="1-based active graph position",
    )
    total_graphs: int = Field(
        ge=0,
        description="Total number of available graphs",
    )
    active_running_state: RunningState = Field(
        description="Running state of active graph only (not background graphs)",
    )

    @field_validator("active_position")
    @classmethod
    def _validate_active_position(cls, value: int) -> int:
        if value < 1:
            raise ValueError("active_position must be >= 1")

        return value

    @field_validator("total_graphs")
    @classmethod
    def _validate_total_graphs(cls, value: int) -> int:
        if value < 0:
            raise ValueError("total_graphs must be >= 0")

        return value

    @classmethod
    def from_execution_status(
        cls,
        active_position: int,
        total_graphs: int,
        execution_status: ExecutionStatus,
    ) -> MultiGraphStatusSnapshot:
        """Create a MultiGraphStatusSnapshot from an ExecutionStatus.

        Args:
            active_position: 1-based position of the active graph
            total_graphs: Total number of graphs
            execution_status: ExecutionStatus from the active graph

        Returns:
            MultiGraphStatusSnapshot with converted running state
        """
        running_state = RunningState(execution_status.value)

        return cls(
            active_position=active_position,
            total_graphs=total_graphs,
            active_running_state=running_state,
        )
