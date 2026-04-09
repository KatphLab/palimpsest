"""Parallel graph execution service with session management.

This module provides the MultiGraphExecutor which manages GraphSession objects
through the GraphRegistry. It coordinates multi-graph execution, navigation,
and status control for the TUI multi-graph forking feature.
"""

from __future__ import annotations

import logging
import threading
from threading import RLock
from typing import Callable

from models.execution import ExecutionState, ExecutionStatus
from models.graph_session import GraphSession
from models.status_snapshot import StatusSnapshot
from runtime.graph_registry import GraphNotFoundError, GraphRegistry, NoActiveGraphError
from utils.time import utc_now

__all__ = [
    "GraphNotFoundError",
    "MaxParallelExceeded",
    "MultiGraphExecutor",
]


class MaxParallelExceeded(RuntimeError):
    """Raised when attempting to run more than max parallel graphs."""


class MultiGraphExecutor:
    """Execute and manage multiple graph sessions with the GraphRegistry.

    This executor provides:
    - GraphSession registration and management
    - Cyclic navigation support (Tab/Shift+Tab)
    - Single active graph enforcement
    - Execution status control (start, pause, resume, stop)
    - Status snapshot generation for TUI rendering

    The executor delegates session storage and navigation to the GraphRegistry,
    focusing on execution coordination and status management.
    """

    def __init__(
        self,
        *,
        graph_registry: GraphRegistry | None = None,
        max_parallel: int = 10,
        logger: logging.Logger | None = None,
        auto_execute_interval: float = 0.01,
    ) -> None:
        """Initialize the multi-graph executor.

        Args:
            graph_registry: Optional GraphRegistry instance. Creates default if None.
            max_parallel: Maximum number of parallel graph sessions allowed.
            logger: Optional logger instance.
            auto_execute_interval: Interval in seconds between auto-execution cycles
                for background graph progression. Set to 0 to disable auto-execution.

        Raises:
            ValueError: If max_parallel is not between 1 and 50.
        """
        if max_parallel < 1 or max_parallel > 50:
            raise ValueError(
                f"max_parallel must be between 1 and 50, got {max_parallel}"
            )

        self._registry = (
            graph_registry if graph_registry is not None else GraphRegistry()
        )
        self._max_parallel = max_parallel
        self._logger = logger if logger is not None else logging.getLogger(__name__)
        self._lock = RLock()

        # Background execution support
        self._auto_execute_interval = auto_execute_interval
        self._background_thread: threading.Thread | None = None
        self._stop_background = threading.Event()
        self._execution_callback: Callable[[str], None] | None = None

    def register_graph(
        self,
        session: GraphSession,
    ) -> GraphSession:
        """Register a GraphSession and return a defensive copy.

        If this is the first session, it becomes active automatically.

        Args:
            session: The GraphSession to register.

        Returns:
            Defensive copy of the registered session.

        Raises:
            MaxParallelExceeded: If max_parallel limit would be exceeded.
            ValueError: If session graph_id is invalid or already registered.
        """
        with self._lock:
            if self._registry.get_session_count() >= self._max_parallel:
                raise MaxParallelExceeded(
                    f"Maximum parallel graphs reached ({self._max_parallel})"
                )

            return self._registry.register_session(session)

    def get_session(self, graph_id: str) -> GraphSession | None:
        """Get a GraphSession by ID.

        Args:
            graph_id: The graph ID to look up.

        Returns:
            Defensive copy of the GraphSession, or None if not found.
        """
        with self._lock:
            try:
                return self._registry.get_session(graph_id)
            except GraphNotFoundError:
                return None

    def get_session_count(self) -> int:
        """Return the number of registered sessions."""
        with self._lock:
            return self._registry.get_session_count()

    def get_active_session(self) -> GraphSession | None:
        """Get the currently active GraphSession.

        Returns:
            Defensive copy of the active session, or None if no sessions exist.
        """
        with self._lock:
            try:
                return self._registry.get_active_session()
            except NoActiveGraphError:
                return None

    def set_active_session(self, graph_id: str) -> GraphSession:
        """Set a specific graph as the active session.

        Args:
            graph_id: The graph ID to activate.

        Returns:
            Defensive copy of the newly active session.

        Raises:
            GraphNotFoundError: If session not found.
        """
        with self._lock:
            return self._registry.set_active_session(graph_id)

    def switch_to_next(self) -> GraphSession:
        """Switch to the next graph in cyclic order (Tab navigation).

        Returns:
            Defensive copy of the newly active session.

        Raises:
            NoActiveGraphError: If no graphs are registered.
        """
        with self._lock:
            return self._registry.switch_to_next()

    def switch_to_previous(self) -> GraphSession:
        """Switch to the previous graph in cyclic order (Shift+Tab navigation).

        Returns:
            Defensive copy of the newly active session.

        Raises:
            NoActiveGraphError: If no graphs are registered.
        """
        with self._lock:
            return self._registry.switch_to_previous()

    def start_graph(self, graph_id: str) -> GraphSession:
        """Start execution of a graph session (set status to RUNNING).

        Args:
            graph_id: The graph ID to start.

        Returns:
            Defensive copy of the updated session.

        Raises:
            GraphNotFoundError: If session not found.
        """
        with self._lock:
            session = self._registry.get_session(graph_id)
            session.execution_status = ExecutionStatus.RUNNING
            session.last_activity_at = utc_now()
            updated = self._registry.update_session(session)
            self._maybe_start_background_execution()
            return updated

    def pause_graph(self, graph_id: str) -> GraphSession:
        """Pause execution of a graph session (set status to PAUSED).

        Args:
            graph_id: The graph ID to pause.

        Returns:
            Defensive copy of the updated session.

        Raises:
            GraphNotFoundError: If session not found.
        """
        with self._lock:
            session = self._registry.get_session(graph_id)
            session.execution_status = ExecutionStatus.PAUSED
            session.last_activity_at = utc_now()
            updated = self._registry.update_session(session)
            self._maybe_stop_background_execution()
            return updated

    def resume_graph(self, graph_id: str) -> GraphSession:
        """Resume execution of a paused graph session (set status to RUNNING).

        Args:
            graph_id: The graph ID to resume.

        Returns:
            Defensive copy of the updated session.

        Raises:
            GraphNotFoundError: If session not found.
        """
        with self._lock:
            session = self._registry.get_session(graph_id)
            session.execution_status = ExecutionStatus.RUNNING
            session.last_activity_at = utc_now()
            updated = self._registry.update_session(session)
            self._maybe_start_background_execution()
            return updated

    def stop_graph(self, graph_id: str) -> GraphSession:
        """Stop execution of a graph session (set status to IDLE).

        Args:
            graph_id: The graph ID to stop.

        Returns:
            Defensive copy of the updated session.

        Raises:
            GraphNotFoundError: If session not found.
        """
        with self._lock:
            session = self._registry.get_session(graph_id)
            session.execution_status = ExecutionStatus.IDLE
            session.last_activity_at = utc_now()
            updated = self._registry.update_session(session)
            self._maybe_stop_background_execution()
            return updated

    def remove_session(self, graph_id: str) -> None:
        """Remove a GraphSession from the executor.

        If the removed session was active, the next session becomes active.

        Args:
            graph_id: The graph ID to remove.
        """
        with self._lock:
            self._registry.remove_session(graph_id)
            self._maybe_stop_background_execution()

    def list_sessions(self) -> list[GraphSession]:
        """Get all registered sessions in order.

        Returns:
            List of defensive copies of all sessions in order.
        """
        with self._lock:
            return self._registry.list_sessions()

    def get_execution_state(self, graph_id: str) -> ExecutionState | None:
        """Return current execution state for the requested graph.

        This provides backward-compatible ExecutionState from GraphSession.

        Args:
            graph_id: The graph ID to look up.

        Returns:
            ExecutionState if session exists, None otherwise.
        """
        with self._lock:
            try:
                session = self._registry.get_session(graph_id)
            except GraphNotFoundError:
                return None

            return _session_to_execution_state(session)

    def get_all_execution_states(self) -> list[ExecutionState]:
        """Return execution states for all tracked sessions.

        Returns:
            List of ExecutionState objects for all sessions.
        """
        with self._lock:
            sessions = self._registry.list_sessions()
            return [_session_to_execution_state(s) for s in sessions]

    def get_status_snapshot(self) -> StatusSnapshot:
        """Get a status snapshot for TUI rendering.

        Returns:
            StatusSnapshot with active position, total graphs, and running state.
        """
        with self._lock:
            return self._registry.get_status_snapshot()

    def execute(self, graph_id: str) -> ExecutionState:
        """Alias for start_graph that returns ExecutionState.

        Args:
            graph_id: The graph ID to execute.

        Returns:
            ExecutionState of the started graph.

        Raises:
            GraphNotFoundError: If session not found.
        """
        session = self.start_graph(graph_id)
        return _session_to_execution_state(session)

    def pause(self, graph_id: str) -> ExecutionState:
        """Alias for pause_graph that returns ExecutionState.

        Args:
            graph_id: The graph ID to pause.

        Returns:
            ExecutionState of the paused graph.

        Raises:
            GraphNotFoundError: If session not found.
        """
        session = self.pause_graph(graph_id)
        return _session_to_execution_state(session)

    def resume(self, graph_id: str) -> ExecutionState:
        """Alias for resume_graph that returns ExecutionState.

        Args:
            graph_id: The graph ID to resume.

        Returns:
            ExecutionState of the resumed graph.

        Raises:
            GraphNotFoundError: If session not found.
        """
        session = self.resume_graph(graph_id)
        return _session_to_execution_state(session)

    def stop(self, graph_id: str) -> ExecutionState:
        """Alias for stop_graph that returns ExecutionState.

        Args:
            graph_id: The graph ID to stop.

        Returns:
            ExecutionState of the stopped graph.

        Raises:
            GraphNotFoundError: If session not found.
        """
        session = self.stop_graph(graph_id)
        return _session_to_execution_state(session)

    def execute_all(self) -> list[GraphSession]:
        """Execute one cycle for all running graphs regardless of focus.

        This method advances all graphs with RUNNING status, updating their
        last_activity_at timestamp. This enables background execution where
        inactive graphs continue to progress while not focused.

        Returns:
            List of defensive copies of updated running sessions.
        """
        with self._lock:
            updated_sessions: list[GraphSession] = []
            now = utc_now()
            sessions = self._registry.list_sessions()

            for session in sessions:
                if session.execution_status == ExecutionStatus.RUNNING:
                    session.last_activity_at = now
                    updated = self._registry.update_session(session)
                    updated_sessions.append(updated)

            return updated_sessions

    def start_background_execution(
        self, execution_callback: Callable[[str], None] | None = None
    ) -> None:
        """Start the background execution thread.

        This enables automatic progression of all running graphs regardless
        of which graph is currently active/focused.

        Args:
            execution_callback: Optional callback invoked for each graph
                that is executed during background cycles.
        """
        with self._lock:
            if (
                self._background_thread is not None
                and self._background_thread.is_alive()
            ):
                return  # Already running

            self._execution_callback = execution_callback
            self._stop_background.clear()
            self._background_thread = threading.Thread(
                target=self._background_execution_loop,
                daemon=True,
                name="MultiGraphExecutor-Background",
            )
            self._background_thread.start()
            self._logger.debug("Background execution started")

    def stop_background_execution(self) -> None:
        """Stop the background execution thread."""
        background_thread: threading.Thread | None = None
        with self._lock:
            if self._background_thread is None:
                return

            self._stop_background.set()
            background_thread = self._background_thread

        assert background_thread is not None
        background_thread.join(timeout=1.0)

        with self._lock:
            if self._background_thread is background_thread:
                if background_thread.is_alive():
                    self._logger.warning(
                        "Background execution thread did not stop within timeout"
                    )
                else:
                    self._background_thread = None
            self._logger.debug("Background execution stopped")

    def _background_execution_loop(self) -> None:
        """Background thread loop that executes all running graphs."""
        if self._auto_execute_interval <= 0:
            return

        while not self._stop_background.is_set():
            try:
                running_sessions = self.execute_all()
                if self._execution_callback:
                    for session in running_sessions:
                        self._execution_callback(session.graph_id)
            except Exception as error:
                self._logger.warning("Background execution error: %s", error)

            # Wait for the interval or until stopped
            self._stop_background.wait(self._auto_execute_interval)

    def _maybe_start_background_execution(self) -> None:
        """Start background execution if there are running graphs and interval > 0."""
        if self._auto_execute_interval <= 0:
            return

        # Check if any graph is running
        has_running = any(
            s.execution_status == ExecutionStatus.RUNNING
            for s in self._registry.list_sessions()
        )

        if has_running:
            self.start_background_execution()

    def _maybe_stop_background_execution(self) -> None:
        """Stop background execution if no running graphs remain."""
        # Check if any graph is still running
        has_running = any(
            s.execution_status == ExecutionStatus.RUNNING
            for s in self._registry.list_sessions()
        )

        if not has_running:
            self.stop_background_execution()


def _session_to_execution_state(session: GraphSession) -> ExecutionState:
    """Convert a GraphSession to an ExecutionState.

    This provides backward compatibility for code expecting ExecutionState.

    Args:
        session: The GraphSession to convert.

    Returns:
        ExecutionState representing the session.
    """
    return ExecutionState(
        graph_id=session.graph_id,
        status=session.execution_status,
        current_node_id=session.current_node_id,
        completed_nodes=0,  # Sessions don't track completed nodes
        total_nodes=0,  # Sessions don't track total nodes
        progress=0.0,  # Sessions don't track progress
        started_at=None,
        last_activity=session.last_activity_at,
    )
