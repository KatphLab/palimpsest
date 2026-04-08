"""Parallel graph execution service with isolation and conflict handling."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from pathlib import Path

from networkx.readwrite import json_graph

from models.execution import (
    RESOURCE_LIMITS,
    ConflictHandler,
    ConflictInfo,
    ConflictResolution,
    ConflictSnapshot,
    ExecutionState,
    ExecutionStatus,
    ExecutionStepResult,
    ParallelExecutionState,
    ResourceUsage,
)
from models.graph_instance import GraphInstance
from persistence.graph_store import GraphStore
from runtime.graph_registry import GraphRegistry
from utils.time import utc_now

__all__ = [
    "GraphNotFoundError",
    "LastWriteWinsConflictHandler",
    "MaxParallelExceeded",
    "MultiGraphExecutor",
]


class GraphNotFoundError(FileNotFoundError):
    """Raised when an operation targets a missing graph instance."""


class MaxParallelExceeded(RuntimeError):
    """Raised when attempting to run more than max parallel graphs."""


class LastWriteWinsConflictHandler(ConflictHandler):
    """Conflict handler using optimistic locking with last-write-wins."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger if logger is not None else logging.getLogger(__name__)

    async def detect_conflicts(
        self,
        graph_id: str,
        local_state: ConflictSnapshot,
        remote_state: ConflictSnapshot,
    ) -> ConflictInfo | None:
        """Detect a conflict when remote data is newer than local state."""

        if remote_state.last_modified <= local_state.last_modified:
            return None

        fields: list[str] = ["lastModified"]
        if local_state.metadata != remote_state.metadata:
            fields.append("metadata")

        return ConflictInfo(
            graph_id=graph_id,
            last_local_modified=local_state.last_modified,
            last_remote_modified=remote_state.last_modified,
            conflicting_fields=fields,
        )

    async def resolve_conflict(
        self,
        conflict: ConflictInfo,
        strategy: ConflictResolution,
        local_state: ConflictSnapshot,
        remote_state: ConflictSnapshot,
    ) -> ConflictSnapshot:
        """Resolve conflict according to the requested strategy."""

        if strategy == ConflictResolution.ACCEPT_REMOTE:
            return remote_state

        if strategy == ConflictResolution.MANUAL_MERGE:
            self._logger.info(
                "manual conflict merge requested for graph %s; defaulting to local",
                conflict.graph_id,
            )

        return local_state

    def notify_conflict(self, conflict: ConflictInfo) -> None:
        """Emit a non-blocking user-visible warning for conflicts."""

        self._logger.warning(
            "Conflict detected for graph %s (local=%s, remote=%s, fields=%s)",
            conflict.graph_id,
            conflict.last_local_modified.isoformat(),
            conflict.last_remote_modified.isoformat(),
            ",".join(conflict.conflicting_fields),
        )


class MultiGraphExecutor:
    """Execute multiple graph instances with strict state isolation."""

    def __init__(
        self,
        *,
        graph_store: GraphStore | None = None,
        graph_registry: GraphRegistry | None = None,
        conflict_handler: ConflictHandler | None = None,
        root_dir: Path | None = None,
        max_parallel: int = RESOURCE_LIMITS["max_parallel_graphs"],
        logger: logging.Logger | None = None,
    ) -> None:
        if max_parallel < 1 or max_parallel > RESOURCE_LIMITS["max_supported_graphs"]:
            raise ValueError(
                "max_parallel must be between 1 and "
                f"{RESOURCE_LIMITS['max_supported_graphs']}"
            )

        storage_root = root_dir if root_dir is not None else Path.cwd()
        self._graph_store = (
            graph_store
            if graph_store is not None
            else GraphStore(root_dir=storage_root)
        )
        self._graph_registry = (
            graph_registry if graph_registry is not None else GraphRegistry()
        )
        self._logger = logger if logger is not None else logging.getLogger(__name__)
        self._conflict_handler = (
            conflict_handler
            if conflict_handler is not None
            else LastWriteWinsConflictHandler(self._logger)
        )
        self._max_parallel = max_parallel
        self._states: dict[str, ExecutionState] = {}
        self._graph_locks: dict[str, asyncio.Lock] = {}
        self._known_snapshots: dict[str, ConflictSnapshot] = {}
        self._resource_usage = ResourceUsage(
            active_graphs=0,
            total_memory_mb=0.0,
            cpu_percent=0.0,
            warning=None,
        )

    def execute(self, graph_id: str, entry_node: str | None = None) -> ExecutionState:
        """Alias for ``execute_graph``."""

        return self.execute_graph(graph_id, entry_node)

    def pause(self, graph_id: str) -> ExecutionState:
        """Alias for ``pause_graph``."""

        return self.pause_graph(graph_id)

    def resume(self, graph_id: str) -> ExecutionState:
        """Alias for ``resume_graph``."""

        return self.resume_graph(graph_id)

    def stop(self, graph_id: str) -> ExecutionState:
        """Alias for ``stop_graph``."""

        return self.stop_graph(graph_id)

    def execute_graph(
        self,
        graph_id: str,
        entry_node: str | None = None,
    ) -> ExecutionState:
        """Begin or resume execution of a graph instance."""

        existing = self._states.get(graph_id)
        if existing is None:
            if self._running_count() >= self._max_parallel:
                raise MaxParallelExceeded(
                    f"maximum parallel executions reached ({self._max_parallel})"
                )
            graph = self._load_graph(graph_id)
            nodes = list(graph.graph_data.nodes())
            if entry_node is not None and entry_node not in nodes:
                raise ValueError(f"entry node does not exist in graph: {entry_node}")

            initial_node = (
                entry_node if entry_node is not None else _first_node_id(nodes)
            )
            now = utc_now()
            self._graph_registry.register(graph)
            self._known_snapshots[graph_id] = ConflictSnapshot(
                last_modified=graph.last_modified,
                metadata=graph.metadata,
            )
            state = ExecutionState(
                graph_id=graph.id,
                status=ExecutionStatus.RUNNING,
                current_node_id=initial_node,
                completed_nodes=0,
                total_nodes=len(nodes),
                progress=_compute_progress(completed_nodes=0, total_nodes=len(nodes)),
                started_at=now,
                last_activity=now,
            )
            self._states[graph_id] = state
            self._graph_locks.setdefault(graph_id, asyncio.Lock())
            self._update_resource_usage()
            return state.model_copy(deep=True)

        if existing.status == ExecutionStatus.PAUSED:
            existing.status = ExecutionStatus.RUNNING
            existing.last_activity = utc_now()
        self._update_resource_usage()
        return existing.model_copy(deep=True)

    def pause_graph(self, graph_id: str) -> ExecutionState:
        """Pause execution of a graph instance."""

        state = self._require_state(graph_id)
        if state.status == ExecutionStatus.RUNNING:
            state.status = ExecutionStatus.PAUSED
            state.last_activity = utc_now()
        self._update_resource_usage()
        return state.model_copy(deep=True)

    def resume_graph(self, graph_id: str) -> ExecutionState:
        """Resume execution of a paused graph instance."""

        state = self._require_state(graph_id)
        if state.status == ExecutionStatus.PAUSED:
            state.status = ExecutionStatus.RUNNING
            state.last_activity = utc_now()
        self._update_resource_usage()
        return state.model_copy(deep=True)

    def stop_graph(self, graph_id: str) -> ExecutionState:
        """Stop execution of a graph instance while preserving progress state."""

        state = self._require_state(graph_id)
        state.status = ExecutionStatus.IDLE
        state.last_activity = utc_now()
        self._update_resource_usage()
        return state.model_copy(deep=True)

    def get_execution_state(self, graph_id: str) -> ExecutionState | None:
        """Return current execution state for the requested graph."""

        state = self._states.get(graph_id)
        if state is None:
            return None

        return state.model_copy(deep=True)

    def get_all_execution_states(self) -> ParallelExecutionState:
        """Return combined execution state for all tracked graphs."""

        ordered = [self._states[graph_id] for graph_id in sorted(self._states)]
        return ParallelExecutionState(
            executions=ordered,
            active_count=self._running_count(),
            max_parallel=self._max_parallel,
        )

    async def advance_step(
        self,
        graph_id: str,
    ) -> tuple[ExecutionState, ExecutionStepResult]:
        """Advance one execution step while preserving graph isolation."""

        state = self._require_state(graph_id)
        if state.status == ExecutionStatus.PAUSED:
            raise ValueError("cannot advance a paused graph")
        if state.status == ExecutionStatus.IDLE:
            raise ValueError("cannot advance a stopped graph")
        if state.status == ExecutionStatus.ERROR:
            raise ValueError("cannot advance a graph in error state")

        if state.status == ExecutionStatus.COMPLETED:
            return state.model_copy(deep=True), ExecutionStepResult(
                executed_node_id=None,
                completed=True,
            )

        lock = self._graph_locks.setdefault(graph_id, asyncio.Lock())
        async with lock:
            local_graph = self._graph_registry.get(graph_id)
            violation = self._graph_registry.detect_isolation_violation(graph_id)
            if violation is not None:
                raise ValueError(violation.description)

            remote_graph = self._load_graph(graph_id)
            local_snapshot = self._known_snapshots.get(graph_id)
            if local_snapshot is None:
                local_snapshot = ConflictSnapshot(
                    last_modified=local_graph.last_modified,
                    metadata=local_graph.metadata,
                )

            remote_snapshot = ConflictSnapshot(
                last_modified=remote_graph.last_modified,
                metadata=remote_graph.metadata,
            )
            conflict = await self._conflict_handler.detect_conflicts(
                graph_id,
                local_snapshot,
                remote_snapshot,
            )
            if conflict is not None:
                self._conflict_handler.notify_conflict(conflict)
                resolved = await self._conflict_handler.resolve_conflict(
                    conflict,
                    ConflictResolution.KEEP_LOCAL,
                    local_snapshot,
                    remote_snapshot,
                )
                if resolved == remote_snapshot:
                    local_graph = remote_graph

            nodes = list(local_graph.graph_data.nodes())
            total_nodes = len(nodes)
            executed_node_id: str | None = None
            completed_nodes = state.completed_nodes
            if completed_nodes < total_nodes:
                executed_node_id = str(nodes[completed_nodes])
                node_payload = local_graph.graph_data.nodes[nodes[completed_nodes]]
                current_count = int(node_payload.get("execution_count", 0))
                node_payload["execution_count"] = current_count + 1
                local_graph.metadata["lastExecutedNodeId"] = executed_node_id
                completed_nodes += 1

            now = utc_now()
            local_graph.last_modified = now
            self._graph_store.save(local_graph)
            self._graph_registry.update(local_graph)
            self._known_snapshots[graph_id] = ConflictSnapshot(
                last_modified=local_graph.last_modified,
                metadata=local_graph.metadata,
            )

            state.completed_nodes = completed_nodes
            state.total_nodes = total_nodes
            state.progress = _compute_progress(
                completed_nodes=completed_nodes,
                total_nodes=total_nodes,
            )
            state.current_node_id = executed_node_id
            state.last_activity = now
            state.status = (
                ExecutionStatus.COMPLETED
                if total_nodes == 0 or completed_nodes >= total_nodes
                else ExecutionStatus.RUNNING
            )

            self._update_resource_usage()
            return state.model_copy(deep=True), ExecutionStepResult(
                executed_node_id=executed_node_id,
                completed=state.status == ExecutionStatus.COMPLETED,
            )

    def get_resource_usage(self) -> ResourceUsage:
        """Return current tracked resource usage and warning state."""

        self._update_resource_usage()
        return self._resource_usage.model_copy(deep=True)

    def _require_state(self, graph_id: str) -> ExecutionState:
        state = self._states.get(graph_id)
        if state is None:
            raise GraphNotFoundError(f"graph not executing: {graph_id}")

        return state

    def _load_graph(self, graph_id: str) -> GraphInstance:
        try:
            return self._graph_store.load(graph_id)
        except FileNotFoundError as error:
            raise GraphNotFoundError(str(error)) from error

    def _running_count(self) -> int:
        return sum(
            1
            for state in self._states.values()
            if state.status == ExecutionStatus.RUNNING
        )

    def _active_count(self) -> int:
        return sum(
            1
            for state in self._states.values()
            if state.status in {ExecutionStatus.RUNNING, ExecutionStatus.PAUSED}
        )

    def _update_resource_usage(self) -> None:
        active_graphs = self._active_count()
        total_memory_mb = sum(
            _estimate_graph_memory_mb(graph)
            for graph in self._graph_registry.all_graphs()
        )
        cpu_percent = min(100.0, float(active_graphs * 10))
        warning = self._resource_warning(active_graphs, total_memory_mb)
        self._resource_usage = ResourceUsage(
            active_graphs=active_graphs,
            total_memory_mb=total_memory_mb,
            cpu_percent=cpu_percent,
            warning=warning,
        )

    def _resource_warning(
        self, active_graphs: int, total_memory_mb: float
    ) -> str | None:
        warnings: list[str] = []
        active_threshold = max(1, math.ceil(self._max_parallel * 0.8))
        if active_graphs >= active_threshold:
            warnings.append(
                f"Approaching parallel graph limit ({active_graphs}/{self._max_parallel})"
            )

        memory_limit_mb = float(
            self._max_parallel * RESOURCE_LIMITS["max_memory_per_graph_mb"]
        )
        if total_memory_mb >= memory_limit_mb * 0.8:
            warnings.append("Approaching memory limit for active graph executions")

        if not warnings:
            return None

        return "; ".join(warnings)


def _compute_progress(*, completed_nodes: int, total_nodes: int) -> float:
    """Compute normalized execution progress in the range [0.0, 1.0]."""

    if total_nodes == 0:
        return 1.0

    return round(completed_nodes / total_nodes, 6)


def _first_node_id(nodes: list[object]) -> str | None:
    """Return the first node identifier from a graph node listing."""

    if not nodes:
        return None

    return str(nodes[0])


def _estimate_graph_memory_mb(graph: GraphInstance) -> float:
    """Estimate graph memory footprint from serialized payload size."""

    graph_payload = json.dumps(
        json_graph.node_link_data(graph.graph_data, edges="links"),
        default=str,
        sort_keys=True,
    )
    metadata_payload = json.dumps(graph.metadata, default=str, sort_keys=True)
    total_bytes = len(graph_payload.encode("utf-8")) + len(
        metadata_payload.encode("utf-8")
    )
    return round(total_bytes / (1024 * 1024), 6)
