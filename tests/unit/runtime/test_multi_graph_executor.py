"""Unit tests for the MultiGraphExecutor with GraphSession integration."""

from __future__ import annotations

from uuid import uuid4

import pytest

from models.execution import ExecutionStatus
from models.graph_session import GraphSession
from runtime.graph_registry import GraphRegistry
from runtime.multi_graph_executor import (
    GraphNotFoundError,
    MaxParallelExceeded,
    MultiGraphExecutor,
)


class TestMultiGraphExecutorInitialization:
    """Tests for MultiGraphExecutor initialization."""

    def test_executor_initializes_with_default_registry(self) -> None:
        """Executor should initialize with default GraphRegistry."""
        executor = MultiGraphExecutor()

        assert executor is not None
        assert executor.get_all_execution_states() is not None

    def test_executor_initializes_with_provided_registry(self) -> None:
        """Executor should use provided GraphRegistry."""
        registry = GraphRegistry()
        executor = MultiGraphExecutor(graph_registry=registry)

        assert executor is not None

    def test_executor_validates_max_parallel(self) -> None:
        """Executor should validate max_parallel parameter."""
        with pytest.raises(ValueError, match="max_parallel must be between"):
            MultiGraphExecutor(max_parallel=0)

        with pytest.raises(ValueError, match="max_parallel must be between"):
            MultiGraphExecutor(max_parallel=100)


class TestMultiGraphExecutorSessionManagement:
    """Tests for graph session registration and management."""

    def test_register_graph_creates_session(self) -> None:
        """register_graph should create and register a GraphSession."""
        executor = MultiGraphExecutor()
        graph_id = str(uuid4())
        session = GraphSession(
            graph_id=graph_id,
            current_node_id="node-1",
            execution_status=ExecutionStatus.IDLE,
        )

        result = executor.register_graph(session)

        assert result.graph_id == graph_id
        assert result.execution_status == ExecutionStatus.IDLE
        assert executor.get_session_count() == 1

    def test_register_graph_rejects_duplicate(self) -> None:
        """register_graph should reject duplicate graph_id."""
        executor = MultiGraphExecutor()
        graph_id = str(uuid4())
        session = GraphSession(
            graph_id=graph_id,
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session)

        with pytest.raises(ValueError, match="already registered"):
            executor.register_graph(session)

    def test_get_session_returns_session(self) -> None:
        """get_session should return registered session."""
        executor = MultiGraphExecutor()
        graph_id = str(uuid4())
        session = GraphSession(
            graph_id=graph_id,
            current_node_id="node-1",
            execution_status=ExecutionStatus.IDLE,
        )
        executor.register_graph(session)

        result = executor.get_session(graph_id)

        assert result is not None
        assert result.graph_id == graph_id
        assert result.current_node_id == "node-1"

    def test_get_session_returns_none_for_missing(self) -> None:
        """get_session should return None for non-existent graph."""
        executor = MultiGraphExecutor()

        result = executor.get_session(str(uuid4()))

        assert result is None

    def test_get_session_count_returns_correct_count(self) -> None:
        """get_session_count should return number of registered sessions."""
        executor = MultiGraphExecutor()

        assert executor.get_session_count() == 0

        for i in range(3):
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=ExecutionStatus.IDLE,
            )
            executor.register_graph(session)

        assert executor.get_session_count() == 3


class TestMultiGraphExecutorActiveSession:
    """Tests for active session management."""

    def test_first_registered_becomes_active(self) -> None:
        """First registered graph should become active."""
        executor = MultiGraphExecutor()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session)
        active = executor.get_active_session()

        assert active is not None
        assert active.graph_id == session.graph_id
        assert active.is_active

    def test_set_active_session_changes_active(self) -> None:
        """set_active_session should change active session."""
        executor = MultiGraphExecutor()
        session1 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session1)
        executor.register_graph(session2)

        result = executor.set_active_session(session2.graph_id)

        assert result.graph_id == session2.graph_id
        assert result.is_active

        active = executor.get_active_session()
        assert active is not None
        assert active.graph_id == session2.graph_id

    def test_set_active_session_raises_for_missing(self) -> None:
        """set_active_session should raise for non-existent graph."""
        executor = MultiGraphExecutor()

        with pytest.raises(GraphNotFoundError, match="Session not found"):
            executor.set_active_session(str(uuid4()))

    def test_get_active_session_returns_none_when_empty(self) -> None:
        """get_active_session should return None when no sessions."""
        executor = MultiGraphExecutor()

        result = executor.get_active_session()

        assert result is None


class TestMultiGraphExecutorNavigation:
    """Tests for graph navigation (Tab/Shift+Tab)."""

    def test_switch_to_next_moves_to_next_graph(self) -> None:
        """switch_to_next should move to next graph."""
        executor = MultiGraphExecutor()
        session1 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session1)
        executor.register_graph(session2)

        result = executor.switch_to_next()

        assert result.graph_id == session2.graph_id

    def test_switch_to_next_wraps_at_end(self) -> None:
        """switch_to_next should wrap to first at end."""
        executor = MultiGraphExecutor()
        session1 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session1)
        executor.register_graph(session2)
        executor.set_active_session(session2.graph_id)

        result = executor.switch_to_next()

        assert result.graph_id == session1.graph_id

    def test_switch_to_previous_moves_to_previous(self) -> None:
        """switch_to_previous should move to previous graph."""
        executor = MultiGraphExecutor()
        session1 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session3 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session1)
        executor.register_graph(session2)
        executor.register_graph(session3)
        executor.set_active_session(session3.graph_id)

        result = executor.switch_to_previous()

        assert result.graph_id == session2.graph_id

    def test_switch_to_previous_wraps_at_start(self) -> None:
        """switch_to_previous should wrap to last at start."""
        executor = MultiGraphExecutor()
        session1 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session1)
        executor.register_graph(session2)

        result = executor.switch_to_previous()

        assert result.graph_id == session2.graph_id

    def test_switch_single_graph_noop(self) -> None:
        """switch should return current with single graph."""
        executor = MultiGraphExecutor()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session)

        result_next = executor.switch_to_next()
        result_prev = executor.switch_to_previous()

        assert result_next.graph_id == session.graph_id
        assert result_prev.graph_id == session.graph_id

    def test_switch_raises_when_empty(self) -> None:
        """switch should raise when no sessions exist."""
        executor = MultiGraphExecutor()

        from runtime.graph_registry import NoActiveGraphError

        with pytest.raises(NoActiveGraphError):
            executor.switch_to_next()

        with pytest.raises(NoActiveGraphError):
            executor.switch_to_previous()


class TestMultiGraphExecutorStatusControl:
    """Tests for execution status control."""

    def test_start_graph_sets_running_status(self) -> None:
        """start_graph should set session status to RUNNING."""
        executor = MultiGraphExecutor()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        executor.register_graph(session)

        result = executor.start_graph(session.graph_id)

        assert result.execution_status == ExecutionStatus.RUNNING
        retrieved = executor.get_session(session.graph_id)
        assert retrieved is not None
        assert retrieved.execution_status == ExecutionStatus.RUNNING

    def test_pause_graph_sets_paused_status(self) -> None:
        """pause_graph should set session status to PAUSED."""
        executor = MultiGraphExecutor()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.RUNNING,
        )
        executor.register_graph(session)

        result = executor.pause_graph(session.graph_id)

        assert result.execution_status == ExecutionStatus.PAUSED

    def test_resume_graph_sets_running_status(self) -> None:
        """resume_graph should set session status to RUNNING."""
        executor = MultiGraphExecutor()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.PAUSED,
        )
        executor.register_graph(session)

        result = executor.resume_graph(session.graph_id)

        assert result.execution_status == ExecutionStatus.RUNNING

    def test_stop_graph_sets_idle_status(self) -> None:
        """stop_graph should set session status to IDLE."""
        executor = MultiGraphExecutor()
        session = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.RUNNING,
        )
        executor.register_graph(session)

        result = executor.stop_graph(session.graph_id)

        assert result.execution_status == ExecutionStatus.IDLE

    def test_status_control_raises_for_missing(self) -> None:
        """Status control methods should raise for non-existent graph."""
        executor = MultiGraphExecutor()

        with pytest.raises(GraphNotFoundError):
            executor.start_graph(str(uuid4()))

        with pytest.raises(GraphNotFoundError):
            executor.pause_graph(str(uuid4()))

        with pytest.raises(GraphNotFoundError):
            executor.resume_graph(str(uuid4()))

        with pytest.raises(GraphNotFoundError):
            executor.stop_graph(str(uuid4()))


class TestMultiGraphExecutorRemoveSession:
    """Tests for session removal."""

    def test_remove_session_deletes_session(self) -> None:
        """remove_session should delete session from executor."""
        executor = MultiGraphExecutor()
        graph_id = str(uuid4())
        session = GraphSession(
            graph_id=graph_id,
            execution_status=ExecutionStatus.IDLE,
        )
        executor.register_graph(session)

        executor.remove_session(graph_id)

        assert executor.get_session_count() == 0
        assert executor.get_session(graph_id) is None

    def test_remove_active_session_reassigns_active(self) -> None:
        """remove_session for active should reassign to next session."""
        executor = MultiGraphExecutor()
        session1 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session1)
        executor.register_graph(session2)

        executor.remove_session(session1.graph_id)

        active = executor.get_active_session()
        assert active is not None
        assert active.graph_id == session2.graph_id


class TestMultiGraphExecutorExecutionState:
    """Tests for backward-compatible ExecutionState retrieval."""

    def test_get_execution_state_returns_state(self) -> None:
        """get_execution_state should return ExecutionState for session."""
        executor = MultiGraphExecutor()
        session = GraphSession(
            graph_id=str(uuid4()),
            current_node_id="node-1",
            execution_status=ExecutionStatus.RUNNING,
        )
        executor.register_graph(session)

        state = executor.get_execution_state(session.graph_id)

        assert state is not None
        assert state.graph_id == session.graph_id
        assert state.current_node_id == "node-1"

    def test_get_all_execution_states_returns_all(self) -> None:
        """get_all_execution_states should return all session states."""
        executor = MultiGraphExecutor()

        for i in range(3):
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=ExecutionStatus.IDLE,
            )
            executor.register_graph(session)

        states = executor.get_all_execution_states()

        assert len(states) == 3


class TestMultiGraphExecutorMaxParallel:
    """Tests for max parallel enforcement."""

    def test_enforces_max_parallel_limit(self) -> None:
        """Executor should enforce max_parallel limit."""
        executor = MultiGraphExecutor(max_parallel=2)

        # Register max_parallel graphs
        for i in range(2):
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=ExecutionStatus.IDLE,
            )
            executor.register_graph(session)

        # Try to exceed limit
        with pytest.raises(MaxParallelExceeded):
            session = GraphSession(
                graph_id=str(uuid4()),
                execution_status=ExecutionStatus.IDLE,
            )
            executor.register_graph(session)


class TestMultiGraphExecutorDefensiveCopies:
    """Tests for defensive copy behavior."""

    def test_register_graph_returns_defensive_copy(self) -> None:
        """register_graph should return defensive copy."""
        executor = MultiGraphExecutor()
        graph_id = str(uuid4())
        session = GraphSession(
            graph_id=graph_id,
            current_node_id="original",
            execution_status=ExecutionStatus.IDLE,
        )

        result = executor.register_graph(session)
        result.current_node_id = "modified"

        retrieved = executor.get_session(graph_id)
        assert retrieved is not None
        assert retrieved.current_node_id == "original"

    def test_get_session_returns_defensive_copy(self) -> None:
        """get_session should return defensive copy."""
        executor = MultiGraphExecutor()
        graph_id = str(uuid4())
        session = GraphSession(
            graph_id=graph_id,
            execution_status=ExecutionStatus.IDLE,
        )
        executor.register_graph(session)

        result = executor.get_session(graph_id)
        assert result is not None
        result.execution_status = ExecutionStatus.RUNNING

        retrieved = executor.get_session(graph_id)
        assert retrieved is not None
        assert retrieved.execution_status == ExecutionStatus.IDLE

    def test_switch_returns_defensive_copy(self) -> None:
        """switch methods should return defensive copies."""
        executor = MultiGraphExecutor()
        session1 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )
        session2 = GraphSession(
            graph_id=str(uuid4()),
            execution_status=ExecutionStatus.IDLE,
        )

        executor.register_graph(session1)
        executor.register_graph(session2)

        result = executor.switch_to_next()
        result.execution_status = ExecutionStatus.COMPLETED

        retrieved = executor.get_session(session2.graph_id)
        assert retrieved is not None
        assert retrieved.execution_status == ExecutionStatus.IDLE
