"""Models and contracts for multi-graph execution state management."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import ConfigDict, Field, JsonValue, field_validator

from models.common import StrictBaseModel, UTCDateTime
from utils.uuid_validation import ensure_valid_uuid

__all__ = [
    "ConflictHandler",
    "ConflictInfo",
    "ConflictResolution",
    "ConflictSnapshot",
    "ExecutionState",
    "ExecutionStatus",
    "ExecutionStepResult",
    "IsolationViolation",
    "ParallelExecutionState",
    "RESOURCE_LIMITS",
    "ResourceUsage",
]


RESOURCE_LIMITS: dict[str, int] = {
    "max_parallel_graphs": 10,
    "max_supported_graphs": 50,
    "max_nodes_per_graph": 10000,
    "max_memory_per_graph_mb": 100,
    "background_operation_timeout_sec": 30,
}


class ExecutionStatus(StrEnum):
    """Status of a graph execution instance."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ExecutionState(StrictBaseModel):
    """Current execution state for a graph instance."""

    model_config = ConfigDict(extra="forbid")

    graph_id: str = Field(min_length=1)
    status: ExecutionStatus
    current_node_id: str | None = None
    completed_nodes: int = Field(default=0, ge=0)
    total_nodes: int = Field(ge=0)
    progress: float = Field(ge=0.0, le=1.0)
    started_at: UTCDateTime | None = None
    last_activity: UTCDateTime

    @field_validator("graph_id")
    @classmethod
    def _validate_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="graph_id")


class ParallelExecutionState(StrictBaseModel):
    """State of all active graph executions."""

    model_config = ConfigDict(extra="forbid")

    executions: list[ExecutionState] = Field(max_length=50)
    active_count: int = Field(ge=0)
    max_parallel: int = Field(default=10, ge=1, le=50)


class IsolationViolation(StrictBaseModel):
    """Report of an execution isolation breach between two graphs."""

    model_config = ConfigDict(extra="forbid")

    violation_type: str = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    affected_graph_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    detected_at: UTCDateTime

    @field_validator("source_graph_id", "affected_graph_id")
    @classmethod
    def _validate_graph_ids(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="graph_id")


class ConflictInfo(StrictBaseModel):
    """Details about a detected optimistic-locking conflict."""

    model_config = ConfigDict(extra="forbid")

    graph_id: str = Field(min_length=1)
    last_local_modified: UTCDateTime
    last_remote_modified: UTCDateTime
    conflicting_fields: list[str] = Field(default_factory=list)

    @field_validator("graph_id")
    @classmethod
    def _validate_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="graph_id")


class ConflictResolution(StrEnum):
    """Resolution strategy for execution conflicts."""

    KEEP_LOCAL = "keep_local"
    ACCEPT_REMOTE = "accept_remote"
    MANUAL_MERGE = "manual_merge"


class ConflictSnapshot(StrictBaseModel):
    """Typed state snapshot used during conflict detection and resolution."""

    model_config = ConfigDict(extra="forbid")

    last_modified: UTCDateTime
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ConflictHandler(ABC):
    """Interface for conflict detection, notification, and resolution."""

    @abstractmethod
    async def detect_conflicts(
        self,
        graph_id: str,
        local_state: ConflictSnapshot,
        remote_state: ConflictSnapshot,
    ) -> ConflictInfo | None:
        """Detect conflicts between local and remote graph states."""

    @abstractmethod
    async def resolve_conflict(
        self,
        conflict: ConflictInfo,
        strategy: ConflictResolution,
        local_state: ConflictSnapshot,
        remote_state: ConflictSnapshot,
    ) -> ConflictSnapshot:
        """Resolve a detected conflict and return the selected state."""

    @abstractmethod
    def notify_conflict(self, conflict: ConflictInfo) -> None:
        """Notify the user about a non-blocking conflict."""


class ExecutionStepResult(StrictBaseModel):
    """Result details emitted after one graph execution step."""

    model_config = ConfigDict(extra="forbid")

    executed_node_id: str | None = None
    completed: bool


class ResourceUsage(StrictBaseModel):
    """Current resource usage and warning state for parallel execution."""

    model_config = ConfigDict(extra="forbid")

    active_graphs: int = Field(ge=0)
    total_memory_mb: float = Field(ge=0.0)
    cpu_percent: float = Field(ge=0.0, le=100.0)
    warning: str | None = None
