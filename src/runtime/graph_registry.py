"""Registry for active graph instances with isolation and session management.

This module provides the runtime GraphRegistry which manages GraphSession objects
for the TUI multi-graph forking feature. It maintains ordered graph collections,
supports cyclic navigation (Tab/Shift+Tab), and enforces single active graph invariant.
"""

from __future__ import annotations

import logging
from threading import RLock

from pydantic import ConfigDict

from models.common import StrictBaseModel, UTCDateTime
from models.execution import ExecutionStatus
from models.graph_instance import GraphInstance
from models.graph_registry import GraphRegistry as GraphRegistryModel
from models.graph_session import GraphSession
from models.status_snapshot import StatusSnapshot
from utils.time import utc_now
from utils.uuid_validation import ensure_valid_uuid

__all__ = [
    "GraphRegistry",
    "GraphRegistryEntry",
    "GraphNotFoundError",
    "NoActiveGraphError",
]

LOGGER = logging.getLogger(__name__)


class GraphNotFoundError(KeyError):
    """Raised when an operation targets a missing graph session."""


class NoActiveGraphError(RuntimeError):
    """Raised when no active graph exists but one is required."""


class GraphRegistryEntry(StrictBaseModel):
    """Tracked registry entry for one active graph instance."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    graph: GraphInstance
    registered_at: UTCDateTime


class _SessionEntry:
    """Internal wrapper for GraphSession with synchronization."""

    def __init__(
        self,
        session: GraphSession,
        updated_at: UTCDateTime | None = None,
    ) -> None:
        self.session = session
        self.updated_at = updated_at if updated_at is not None else utc_now()


class GraphRegistry:
    """Manage active graph instances and sessions with deep-copy isolation.

    This registry provides:
    - GraphSession management for TUI multi-graph forking
    - Cyclic navigation support (Tab/Shift+Tab)
    - Single active graph enforcement
    """

    def __init__(self) -> None:
        # Original GraphInstance tracking (for execution isolation)
        self._entries: dict[str, GraphRegistryEntry] = {}

        # New GraphSession tracking (for TUI multi-graph management)
        self._sessions: dict[str, _SessionEntry] = {}
        self._ordered_graph_ids: list[str] = []
        self._active_index: int = 0
        self._lock = RLock()

    def _enforce_single_active_session(self) -> None:
        """Keep exactly one active GraphSession aligned to active_index."""

        if not self._ordered_graph_ids:
            self._active_index = 0
            return

        if self._active_index >= len(self._ordered_graph_ids):
            self._active_index = 0

        for entry in self._sessions.values():
            entry.session.is_active = False

        active_id = self._ordered_graph_ids[self._active_index]
        self._sessions[active_id].session.is_active = True

    def register_session(self, session: GraphSession) -> GraphSession:
        """Register a GraphSession and return a defensive copy.

        If this is the first session, it becomes active automatically.

        Args:
            session: The GraphSession to register

        Returns:
            Defensive copy of the registered session

        Raises:
            ValueError: If session graph_id is invalid or already registered
        """
        with self._lock:
            ensure_valid_uuid(session.graph_id, field_name="graph_id")

            if session.graph_id in self._sessions:
                raise ValueError(f"Session already registered: {session.graph_id}")

            # Create isolated copy
            session_copy = session.model_copy(deep=True)
            session_copy.is_active = False

            # If first session, make it active
            if not self._ordered_graph_ids:
                self._active_index = 0

            # Store session
            self._sessions[session.graph_id] = _SessionEntry(session=session_copy)
            self._ordered_graph_ids.append(session.graph_id)
            self._enforce_single_active_session()

            LOGGER.debug(
                "Registered session %s (active=%s, total=%d)",
                session.graph_id,
                self._sessions[session.graph_id].session.is_active,
                len(self._ordered_graph_ids),
            )

            return session_copy.model_copy(deep=True)

    def get_session(self, graph_id: str) -> GraphSession:
        """Get a GraphSession by ID.

        Args:
            graph_id: The graph ID to look up

        Returns:
            Defensive copy of the GraphSession

        Raises:
            GraphNotFoundError: If session not found
        """
        with self._lock:
            entry = self._sessions.get(graph_id)
            if entry is None:
                raise GraphNotFoundError(f"Session not found: {graph_id}")

            return entry.session.model_copy(deep=True)

    def update_session(self, session: GraphSession) -> GraphSession:
        """Update an existing GraphSession.

        Args:
            session: The updated session (must have existing graph_id)

        Returns:
            Defensive copy of the updated session

        Raises:
            GraphNotFoundError: If session not found
        """
        with self._lock:
            if session.graph_id not in self._sessions:
                raise GraphNotFoundError(
                    f"Session not found for update: {session.graph_id}"
                )

            session_copy = session.model_copy(deep=True)
            self._sessions[session.graph_id] = _SessionEntry(
                session=session_copy,
                updated_at=utc_now(),
            )
            self._enforce_single_active_session()

            return self._sessions[session.graph_id].session.model_copy(deep=True)

    def remove_session(self, graph_id: str) -> None:
        """Remove a GraphSession from the registry.

        If the removed session was active, the next session becomes active.
        If no sessions remain, active_index resets to 0.

        Args:
            graph_id: The graph ID to remove
        """
        with self._lock:
            if graph_id not in self._sessions:
                return

            # Remove from ordered list
            try:
                index = self._ordered_graph_ids.index(graph_id)
                self._ordered_graph_ids.pop(index)
                if index < self._active_index:
                    self._active_index -= 1
                elif index == self._active_index and self._active_index >= len(
                    self._ordered_graph_ids
                ):
                    self._active_index = 0
            except ValueError:
                pass

            # Remove from sessions dict
            del self._sessions[graph_id]

            self._enforce_single_active_session()

            LOGGER.debug(
                "Removed session %s (remaining=%d)",
                graph_id,
                len(self._ordered_graph_ids),
            )

    def get_active_session(self) -> GraphSession:
        """Get the currently active GraphSession.

        Returns:
            Defensive copy of the active session

        Raises:
            NoActiveGraphError: If no active session exists
        """
        with self._lock:
            if not self._ordered_graph_ids:
                raise NoActiveGraphError("No active graph session available")

            active_id = self._ordered_graph_ids[self._active_index]
            entry = self._sessions[active_id]

            return entry.session.model_copy(deep=True)

    def set_active_session(self, graph_id: str) -> GraphSession:
        """Set a specific graph as the active session.

        Args:
            graph_id: The graph ID to activate

        Returns:
            Defensive copy of the newly active session

        Raises:
            GraphNotFoundError: If session not found
        """
        with self._lock:
            if graph_id not in self._sessions:
                raise GraphNotFoundError(f"Session not found: {graph_id}")

            # Deactivate current
            if self._ordered_graph_ids:
                current_active_id = self._ordered_graph_ids[self._active_index]
                self._sessions[current_active_id].session.is_active = False

            # Set new active
            self._active_index = self._ordered_graph_ids.index(graph_id)
            self._enforce_single_active_session()

            LOGGER.info(
                "Activated graph session %s at index %d", graph_id, self._active_index
            )

            return self._sessions[graph_id].session.model_copy(deep=True)

    def switch_to_next(self) -> GraphSession:
        """Switch to the next graph in cyclic order (Tab navigation).

        Returns:
            Defensive copy of the newly active session

        Raises:
            NoActiveGraphError: If no graphs are registered
        """
        with self._lock:
            if not self._ordered_graph_ids:
                raise NoActiveGraphError("No graph sessions available to switch")

            if len(self._ordered_graph_ids) == 1:
                # Single graph - return current
                return self.get_active_session()

            # Deactivate current
            current_id = self._ordered_graph_ids[self._active_index]
            self._sessions[current_id].session.is_active = False

            # Compute next index (cyclic)
            self._active_index = (self._active_index + 1) % len(self._ordered_graph_ids)

            # Activate new
            new_id = self._ordered_graph_ids[self._active_index]
            self._enforce_single_active_session()

            LOGGER.debug(
                "Switched to next graph: %s (index %d)", new_id, self._active_index
            )

            return self._sessions[new_id].session.model_copy(deep=True)

    def switch_to_previous(self) -> GraphSession:
        """Switch to the previous graph in cyclic order (Shift+Tab navigation).

        Returns:
            Defensive copy of the newly active session

        Raises:
            NoActiveGraphError: If no graphs are registered
        """
        with self._lock:
            if not self._ordered_graph_ids:
                raise NoActiveGraphError("No graph sessions available to switch")

            if len(self._ordered_graph_ids) == 1:
                # Single graph - return current
                return self.get_active_session()

            # Deactivate current
            current_id = self._ordered_graph_ids[self._active_index]
            self._sessions[current_id].session.is_active = False

            # Compute previous index (cyclic, handles negative)
            self._active_index = (self._active_index - 1) % len(self._ordered_graph_ids)

            # Activate new
            new_id = self._ordered_graph_ids[self._active_index]
            self._enforce_single_active_session()

            LOGGER.debug(
                "Switched to previous graph: %s (index %d)", new_id, self._active_index
            )

            return self._sessions[new_id].session.model_copy(deep=True)

    def list_sessions(self) -> list[GraphSession]:
        """Get all registered sessions in order.

        Returns:
            List of defensive copies of all sessions in order
        """
        with self._lock:
            return [
                self._sessions[graph_id].session.model_copy(deep=True)
                for graph_id in self._ordered_graph_ids
            ]

    def get_session_count(self) -> int:
        """Return the number of registered sessions."""
        with self._lock:
            return len(self._ordered_graph_ids)

    def get_active_index(self) -> int:
        """Return the current active index (0-based)."""
        with self._lock:
            return self._active_index

    def to_model(self) -> GraphRegistryModel:
        """Export registry state to a GraphRegistry model.

        Returns:
            GraphRegistryModel with current state
        """
        with self._lock:
            return GraphRegistryModel(
                graph_ids=list(self._ordered_graph_ids),
                active_index=self._active_index,
            )

    def get_status_snapshot(self) -> StatusSnapshot:
        """Get a snapshot of registry status for TUI rendering.

        Returns:
            StatusSnapshot with active_position, total_graphs, and active_running_state
        """
        with self._lock:
            total = len(self._ordered_graph_ids)
            if total == 0:
                return StatusSnapshot(
                    active_position=1,  # Must be >=1 per model validator
                    total_graphs=0,
                    active_running_state=ExecutionStatus.IDLE,
                )

            active_session = self._sessions[
                self._ordered_graph_ids[self._active_index]
            ].session

            return StatusSnapshot(
                active_position=self._active_index + 1,  # 1-based for display
                total_graphs=total,
                active_running_state=active_session.execution_status,
            )
