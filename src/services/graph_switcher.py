"""Service for switching active graph context with optimistic locking."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter

from models.requests import GraphSwitchRequest
from models.responses import GraphSwitchResponse
from persistence.graph_store import GraphStore
from services.structured_logging import OperationLogEntry, log_operation
from utils.time import utc_now

__all__ = ["GraphSwitcher"]


class GraphSwitcher:
    """Switch active graph state with last-write-wins conflict resolution."""

    def __init__(
        self,
        *,
        graph_store: GraphStore | None = None,
        root_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        storage_root = root_dir if root_dir is not None else Path.cwd()
        self._graph_store = (
            graph_store
            if graph_store is not None
            else GraphStore(root_dir=storage_root)
        )
        self._logger = logger if logger is not None else logging.getLogger(__name__)
        self._active_graph_id: str | None = None
        self._active_last_modified: datetime | None = None

    def switch_graph(self, request: GraphSwitchRequest) -> GraphSwitchResponse:
        """Switch active graph context and return timing and summary metadata."""

        started_at = utc_now()
        timer_started_at = perf_counter()
        previous_graph_id = self._active_graph_id
        conflict_detected = self._detect_conflict(
            preserve_current=request.preserve_current,
            started_at=started_at,
        )

        target_graph = self._graph_store.load(request.target_graph_id)
        self._active_graph_id = target_graph.id
        self._active_last_modified = target_graph.last_modified

        load_time_ms = round((perf_counter() - timer_started_at) * 1000, 3)
        response = GraphSwitchResponse(
            previous_graph_id=previous_graph_id,
            current_graph_id=target_graph.id,
            load_time_ms=load_time_ms,
            graph_summary=target_graph.to_summary(),
        )

        log_operation(
            self._logger,
            OperationLogEntry(
                operation="switch",
                status="success",
                graph_id=target_graph.id,
                started_at=started_at,
                completed_at=utc_now(),
                metadata={
                    "previous_graph_id": previous_graph_id,
                    "preserve_current": request.preserve_current,
                    "conflict_detected": conflict_detected,
                    "conflict_resolution": "last_write_wins",
                },
            ),
        )
        return response

    def _detect_conflict(self, *, preserve_current: bool, started_at: datetime) -> bool:
        """Detect last-modified divergence for the currently active graph."""

        if (
            not preserve_current
            or self._active_graph_id is None
            or self._active_last_modified is None
        ):
            return False

        try:
            latest_active_graph = self._graph_store.load(self._active_graph_id)
        except FileNotFoundError:
            return False

        if latest_active_graph.last_modified <= self._active_last_modified:
            return False

        log_operation(
            self._logger,
            OperationLogEntry(
                operation="switch",
                status="conflict",
                graph_id=self._active_graph_id,
                started_at=started_at,
                completed_at=utc_now(),
                metadata={
                    "conflict_resolution": "last_write_wins",
                    "tracked_last_modified": self._active_last_modified.isoformat(),
                    "current_last_modified": latest_active_graph.last_modified.isoformat(),
                },
            ),
            level=logging.WARNING,
        )
        return True
