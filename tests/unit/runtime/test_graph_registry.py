"""Unit tests for the runtime GraphRegistry with GraphSession management."""

from __future__ import annotations

import threading
import time
from uuid import uuid4

import pytest

from models.graph_registry import GraphRegistry as GraphRegistryModel
from models.graph_session import ExecutionStatus, GraphSession
from runtime.graph_registry import (
    GraphNotFoundError,
    GraphRegistry,
    NoActiveGraphError,
)


class TestGraphRegistrySessionManagement:
    """Tests for GraphSession management in runtime GraphRegistry."""

    def test_register_session_creates_session(self) -> None:
        """register_session should add a new session to the registry."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            current_node_id="node-1",
            execution_status=ExecutionStatus.IDLE,
            is_active=False,
        )

        result = registry.register_session(session)

        assert result.graph_id == session.graph_id
        assert registry.get_session_count() == 1
        assert registry.get_active_index() == 0

    def test_register_first_session_becomes_active(self) -> None:
        """First registered session should automatically become active."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
            is_active=False,
        )

        registry.register_session(session)
        active = registry.get_active_session()

        assert active.is_active is True
        assert active.graph_id == session.graph_id

    def test_register_session_rejects_duplicate(self) -> None:
        """register_session should reject duplicate graph_id."""
        registry = GraphRegistry()
        graph_id = str(uuid4())
        session1 = GraphSession(
            graph_id=graph_id,
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=graph_id,
            execution_status=ExecutionStatus.RUNNING,
        )

        registry.register_session(session1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register_session(session2)

    def test_register_session_rejects_invalid_uuid(self) -> None:
        """GraphSession model rejects invalid UUID at construction time."""
        with pytest.raises(ValueError, match="graph_id"):
            GraphSession(
                graph_id="not-a-valid-uuid",
                execution_status=ExecutionStatus.IDLE,
            )

    def test_get_session_returns_defensive_copy(self) -> None:
        """get_session should return a defensive copy of the session."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            current_node_id="original",
            execution_status=ExecutionStatus.IDLE,
        )
        registry.register_session(session)

        result = registry.get_session(session.graph_id)
        result.current_node_id = "modified"

        retrieved = registry.get_session(session.graph_id)
        assert retrieved.current_node_id == "original"

    def test_get_session_raises_for_missing(self) -> None:
        """get_session should raise GraphNotFoundError for missing session."""
        registry = GraphRegistry()

        with pytest.raises(GraphNotFoundError, match="Session not found"):
            registry.get_session(str(uuid4()))

    def test_update_session_modifies_existing(self) -> None:
        """update_session should modify an existing session."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            current_node_id="original",
            execution_status=ExecutionStatus.IDLE,
        )
        registry.register_session(session)

        updated = session.model_copy(deep=True)
        updated.current_node_id = "updated"
        updated.execution_status = ExecutionStatus.RUNNING

        result = registry.update_session(updated)

        assert result.current_node_id == "updated"
        assert result.execution_status == ExecutionStatus.RUNNING

        retrieved = registry.get_session(session.graph_id)
        assert retrieved.current_node_id == "updated"
        assert retrieved.execution_status == ExecutionStatus.RUNNING

    def test_update_session_raises_for_missing(self) -> None:
        """update_session should raise GraphNotFoundError for missing session."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        with pytest.raises(GraphNotFoundError, match="Session not found"):
            registry.update_session(session)

    def test_update_session_returns_defensive_copy(self) -> None:
        """update_session should return a defensive copy."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        registry.register_session(session)

        result = registry.update_session(session)
        result.execution_status = ExecutionStatus.RUNNING

        retrieved = registry.get_session(session.graph_id)
        assert retrieved.execution_status == ExecutionStatus.IDLE


class TestGraphRegistryActiveSession:
    """Tests for active session management."""

    def test_get_active_session_returns_active(self) -> None:
        """get_active_session should return the currently active session."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)

        active = registry.get_active_session()

        assert active.graph_id == session1.graph_id
        assert active.is_active is True

    def test_get_active_session_raises_when_empty(self) -> None:
        """get_active_session should raise when no sessions exist."""
        registry = GraphRegistry()

        with pytest.raises(NoActiveGraphError, match="No active graph session"):
            registry.get_active_session()

    def test_set_active_session_changes_active(self) -> None:
        """set_active_session should change which session is active."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)

        result = registry.set_active_session(session2.graph_id)

        assert result.graph_id == session2.graph_id
        assert result.is_active is True

        active = registry.get_active_session()
        assert active.graph_id == session2.graph_id

        # Verify previous is no longer active
        session1_updated = registry.get_session(session1.graph_id)
        assert session1_updated.is_active is False

    def test_set_active_session_raises_for_missing(self) -> None:
        """set_active_session should raise for non-existent session."""
        registry = GraphRegistry()

        with pytest.raises(GraphNotFoundError, match="Session not found"):
            registry.set_active_session(str(uuid4()))


class TestGraphRegistryNavigation:
    """Tests for cyclic graph navigation (Tab/Shift+Tab)."""

    def test_switch_to_next_moves_to_next_graph(self) -> None:
        """switch_to_next should move to the next graph in order."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session3 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.register_session(session3)

        result = registry.switch_to_next()

        assert result.graph_id == session2.graph_id
        assert registry.get_active_index() == 1

    def test_switch_to_next_wraps_at_end(self) -> None:
        """switch_to_next should wrap to first graph at end."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.set_active_session(session2.graph_id)

        result = registry.switch_to_next()

        assert result.graph_id == session1.graph_id
        assert registry.get_active_index() == 0

    def test_switch_to_previous_moves_to_previous_graph(self) -> None:
        """switch_to_previous should move to the previous graph."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session3 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.register_session(session3)
        registry.set_active_session(session3.graph_id)

        result = registry.switch_to_previous()

        assert result.graph_id == session2.graph_id
        assert registry.get_active_index() == 1

    def test_switch_to_previous_wraps_at_start(self) -> None:
        """switch_to_previous should wrap to last graph at start."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.set_active_session(session1.graph_id)

        result = registry.switch_to_previous()

        assert result.graph_id == session2.graph_id
        assert registry.get_active_index() == 1

    def test_switch_to_next_single_graph_noop(self) -> None:
        """switch_to_next should return current with single graph."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session)

        result = registry.switch_to_next()

        assert result.graph_id == session.graph_id
        assert registry.get_active_index() == 0

    def test_switch_to_previous_single_graph_noop(self) -> None:
        """switch_to_previous should return current with single graph."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session)

        result = registry.switch_to_previous()

        assert result.graph_id == session.graph_id
        assert registry.get_active_index() == 0

    def test_switch_to_next_raises_when_empty(self) -> None:
        """switch_to_next should raise when no sessions exist."""
        registry = GraphRegistry()

        with pytest.raises(NoActiveGraphError, match="No graph sessions available"):
            registry.switch_to_next()

    def test_switch_to_previous_raises_when_empty(self) -> None:
        """switch_to_previous should raise when no sessions exist."""
        registry = GraphRegistry()

        with pytest.raises(NoActiveGraphError, match="No graph sessions available"):
            registry.switch_to_previous()


class TestGraphRegistrySessionRemoval:
    """Tests for session removal and active session reassignment."""

    def test_remove_session_deletes_session(self) -> None:
        """remove_session should delete the session from registry."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        registry.register_session(session)

        registry.remove_session(session.graph_id)

        assert registry.get_session_count() == 0
        with pytest.raises(GraphNotFoundError):
            registry.get_session(session.graph_id)

    def test_remove_inactive_session_preserves_active(self) -> None:
        """remove_session for inactive session should not change active."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)

        registry.remove_session(session2.graph_id)

        active = registry.get_active_session()
        assert active.graph_id == session1.graph_id
        assert active.is_active is True

    def test_remove_active_session_reassigns_active(self) -> None:
        """remove_session for active should reassign to next session."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session3 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.register_session(session3)

        registry.remove_session(session1.graph_id)

        active = registry.get_active_session()
        assert active.graph_id == session2.graph_id
        assert active.is_active is True

    def test_remove_last_active_session_clears_registry(self) -> None:
        """remove_session for last session should leave empty registry."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        registry.register_session(session)

        registry.remove_session(session.graph_id)

        assert registry.get_session_count() == 0
        assert registry.get_active_index() == 0
        with pytest.raises(NoActiveGraphError):
            registry.get_active_session()

    def test_remove_session_adjusts_index_at_end(self) -> None:
        """remove_session should adjust active_index when removing at end."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session3 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.register_session(session3)
        registry.set_active_session(session3.graph_id)

        registry.remove_session(session3.graph_id)

        assert registry.get_active_index() == 0
        active = registry.get_active_session()
        assert active.graph_id == session1.graph_id

    def test_remove_nonexistent_session_is_noop(self) -> None:
        """remove_session for non-existent graph_id should be a no-op."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        registry.register_session(session)

        registry.remove_session(str(uuid4()))

        assert registry.get_session_count() == 1


class TestGraphRegistryQueries:
    """Tests for registry query methods."""

    def test_list_sessions_returns_ordered_list(self) -> None:
        """list_sessions should return all sessions in registration order."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session3 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.register_session(session3)

        result = registry.list_sessions()

        assert len(result) == 3
        assert result[0].graph_id == session1.graph_id
        assert result[1].graph_id == session2.graph_id
        assert result[2].graph_id == session3.graph_id

    def test_list_sessions_returns_defensive_copies(self) -> None:
        """list_sessions should return defensive copies."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        registry.register_session(session)

        result = registry.list_sessions()
        result[0].execution_status = ExecutionStatus.RUNNING

        retrieved = registry.get_session(session.graph_id)
        assert retrieved.execution_status == ExecutionStatus.IDLE

    def test_list_sessions_empty_registry(self) -> None:
        """list_sessions should return empty list for empty registry."""
        registry = GraphRegistry()

        result = registry.list_sessions()

        assert result == []

    def test_get_session_count_returns_count(self) -> None:
        """get_session_count should return the number of sessions."""
        registry = GraphRegistry()

        assert registry.get_session_count() == 0

        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        registry.register_session(session1)
        assert registry.get_session_count() == 1

        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        registry.register_session(session2)
        assert registry.get_session_count() == 2

    def test_get_active_index_returns_zero_based(self) -> None:
        """get_active_index should return 0-based index."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session)

        assert registry.get_active_index() == 0


class TestGraphRegistryModelExport:
    """Tests for model export functionality."""

    def test_to_model_exports_state(self) -> None:
        """to_model should export current registry state."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.switch_to_next()

        model = registry.to_model()

        assert isinstance(model, GraphRegistryModel)
        assert model.graph_ids == [session1.graph_id, session2.graph_id]
        assert model.active_index == 1
        assert model.total_graphs == 2

    def test_to_model_empty_registry(self) -> None:
        """to_model should handle empty registry."""
        registry = GraphRegistry()

        model = registry.to_model()

        assert model.graph_ids == []
        assert model.active_index == 0
        assert model.total_graphs == 0


class TestGraphRegistryStatusSnapshot:
    """Tests for status snapshot functionality."""

    def test_get_status_snapshot_returns_active_status(self) -> None:
        """get_status_snapshot should return status for active session."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.RUNNING
        )

        registry.register_session(session1)
        registry.register_session(session2)
        registry.switch_to_next()

        snapshot = registry.get_status_snapshot()

        assert snapshot["active_position"] == 2
        assert snapshot["total_graphs"] == 2
        assert snapshot["active_running_state"] == ExecutionStatus.RUNNING

    def test_get_status_snapshot_empty_registry(self) -> None:
        """get_status_snapshot should handle empty registry."""
        registry = GraphRegistry()

        snapshot = registry.get_status_snapshot()

        assert snapshot["active_position"] == 0
        assert snapshot["total_graphs"] == 0
        assert snapshot["active_running_state"] == ExecutionStatus.IDLE

    def test_get_status_snapshot_single_graph(self) -> None:
        """get_status_snapshot should handle single graph."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.COMPLETED
        )

        registry.register_session(session)

        snapshot = registry.get_status_snapshot()

        assert snapshot["active_position"] == 1
        assert snapshot["total_graphs"] == 1
        assert snapshot["active_running_state"] == ExecutionStatus.COMPLETED


class TestGraphRegistryThreadSafety:
    """Tests for thread safety of GraphRegistry operations."""

    def test_concurrent_register_sessions(self) -> None:
        """Multiple threads registering sessions should be safe."""
        registry = GraphRegistry()
        results: list[str] = []
        errors: list[Exception] = []

        def register_session(index: int) -> None:
            try:
                session = GraphSession(
                    graph_id=str(uuid4()),
                    execution_status=ExecutionStatus.IDLE,
                )
                result = registry.register_session(session)
                results.append(result.graph_id)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_session, args=(i,)) for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert registry.get_session_count() == 10

    def test_concurrent_switch_operations(self) -> None:
        """Multiple threads switching graphs should be safe."""
        registry = GraphRegistry()

        # Register multiple sessions
        for _ in range(5):
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=ExecutionStatus.IDLE,
            )
            registry.register_session(session)

        errors: list[Exception] = []

        def switch_next() -> None:
            try:
                registry.switch_to_next()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=switch_next) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        # Registry should still be in valid state
        assert registry.get_session_count() == 5
        assert 0 <= registry.get_active_index() < 5

    def test_concurrent_read_write_operations(self) -> None:
        """Concurrent reads and writes should be safe."""
        registry = GraphRegistry()

        # Pre-populate with some sessions
        for _ in range(3):
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=ExecutionStatus.IDLE,
            )
            registry.register_session(session)

        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(50):
                    _ = registry.get_active_session()
                    _ = registry.list_sessions()
                    _ = registry.get_status_snapshot()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                for _ in range(20):
                    registry.switch_to_next()
                    time.sleep(0.002)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader))
        for _ in range(2):
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert registry.get_session_count() == 3


class TestGraphRegistryDefensiveCopies:
    """Tests for defensive copy behavior across all operations."""

    def test_register_session_returns_defensive_copy(self) -> None:
        """register_session should return a defensive copy."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()),
            current_node_id="original",
            execution_status=ExecutionStatus.IDLE,
        )

        result = registry.register_session(session)
        result.current_node_id = "modified"

        retrieved = registry.get_session(session.graph_id)
        assert retrieved.current_node_id == "original"

    def test_switch_to_next_returns_defensive_copy(self) -> None:
        """switch_to_next should return a defensive copy."""
        registry = GraphRegistry()
        session1 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )
        session2 = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session1)
        registry.register_session(session2)

        result = registry.switch_to_next()
        result.execution_status = ExecutionStatus.COMPLETED

        retrieved = registry.get_session(session2.graph_id)
        assert retrieved.execution_status == ExecutionStatus.IDLE

    def test_get_active_session_returns_defensive_copy(self) -> None:
        """get_active_session should return a defensive copy."""
        registry = GraphRegistry()
        session = GraphSession(
            graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
        )

        registry.register_session(session)

        result = registry.get_active_session()
        result.execution_status = ExecutionStatus.RUNNING

        retrieved = registry.get_active_session()
        assert retrieved.execution_status == ExecutionStatus.IDLE


class TestGraphRegistryEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_register_many_sessions(self) -> None:
        """Registry should handle many sessions."""
        registry = GraphRegistry()
        count = 100

        for i in range(count):
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=ExecutionStatus.IDLE,
                current_node_id=f"node-{i}",
            )
            registry.register_session(session)

        assert registry.get_session_count() == count
        assert len(registry.list_sessions()) == count

    def test_switch_through_all_graphs(self) -> None:
        """Should be able to switch through all graphs and return to start."""
        registry = GraphRegistry()

        for _ in range(5):
            session = GraphSession(
                graph_id=str(uuid4()), execution_status=ExecutionStatus.IDLE
            )
            registry.register_session(session)

        start_id = registry.get_active_session().graph_id

        for _ in range(5):
            registry.switch_to_next()

        end_id = registry.get_active_session().graph_id

        assert start_id == end_id

    def test_session_with_all_execution_statuses(self) -> None:
        """Registry should handle sessions with different execution statuses."""
        registry = GraphRegistry()
        statuses = [
            ExecutionStatus.IDLE,
            ExecutionStatus.RUNNING,
            ExecutionStatus.PAUSED,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
        ]

        for status in statuses:
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=status,
            )
            registry.register_session(session)

        assert registry.get_session_count() == 5

        for session in registry.list_sessions():
            assert session.execution_status in statuses
