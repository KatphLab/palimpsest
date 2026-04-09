"""Tests for session runtime active graph context integration with multi-graph system."""

from __future__ import annotations

from graph.session_graph import SessionGraph
from models.execution import ExecutionStatus
from models.graph_session import GraphSession
from models.requests import (
    ForkFromCurrentNodeRequest,
    GraphNavigationDirection,
    GraphSwitchRequest,
)
from models.responses import MultiGraphStatusSnapshot, RunningState
from runtime.graph_registry import GraphRegistry
from runtime.session_runtime import SessionRuntime


def test_session_runtime_initializes_with_empty_graph_registry() -> None:
    """Runtime should initialize with an empty graph registry for multi-graph management."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    # Should have a graph_registry attribute
    assert hasattr(runtime, "graph_registry")
    # Should be a GraphRegistry instance
    assert isinstance(runtime.graph_registry, GraphRegistry)
    # Should start empty
    assert runtime.graph_registry.get_session_count() == 0


def test_session_runtime_initializes_with_provided_graph_registry() -> None:
    """Runtime should accept and use a provided graph registry."""
    registry = GraphRegistry()
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
        is_active=True,
    )
    registry.register_session(session)

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        graph_registry=registry,
    )

    # Should use the provided registry
    assert runtime.graph_registry is registry
    # Should have the pre-registered session
    assert runtime.graph_registry.get_session_count() == 1


def test_session_runtime_get_active_graph_session_returns_none_when_empty() -> None:
    """Should return None when no active graph session exists."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    result = runtime.get_active_graph_session()

    assert result is None


def test_session_runtime_get_active_graph_session_returns_active_session() -> None:
    """Should return the currently active GraphSession."""
    runtime = SessionRuntime(session_graph=SessionGraph())
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
        is_active=True,
    )
    runtime.graph_registry.register_session(session)

    result = runtime.get_active_graph_session()

    assert result is not None
    assert result.graph_id == "550e8400-e29b-41d4-a716-446655440000"
    assert result.is_active is True


def test_session_runtime_register_graph_session_adds_to_registry() -> None:
    """Should register a new graph session in the registry."""
    runtime = SessionRuntime(session_graph=SessionGraph())
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.IDLE,
    )

    result = runtime.register_graph_session(session)

    assert result.graph_id == session.graph_id
    assert runtime.graph_registry.get_session_count() == 1
    # First session should be active
    assert result.is_active is True


def test_session_runtime_switch_to_next_graph_updates_active() -> None:
    """Should switch to next graph and update active context."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    # Register two sessions
    session1 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    session2 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440002",
        current_node_id="node-2",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session1)
    runtime.register_graph_session(session2)

    # Switch to next
    result = runtime.switch_to_next_graph()

    assert result.graph_id == session2.graph_id
    assert result.is_active is True
    # Verify the active session changed in registry
    active = runtime.get_active_graph_session()
    assert active is not None
    assert active.graph_id == session2.graph_id


def test_session_runtime_switch_to_previous_graph_updates_active() -> None:
    """Should switch to previous graph and update active context."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    # Register two sessions
    session1 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    session2 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440002",
        current_node_id="node-2",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session1)
    runtime.register_graph_session(session2)
    # Switch to next first to make session2 active
    runtime.switch_to_next_graph()

    # Switch to previous
    result = runtime.switch_to_previous_graph()

    assert result.graph_id == session1.graph_id
    assert result.is_active is True


def test_session_runtime_get_multi_graph_status_snapshot_returns_snapshot() -> None:
    """Should return MultiGraphStatusSnapshot for TUI rendering."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    # Register sessions
    session1 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    session2 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440002",
        current_node_id="node-2",
        execution_status=ExecutionStatus.PAUSED,
    )
    runtime.register_graph_session(session1)
    runtime.register_graph_session(session2)

    result = runtime.get_multi_graph_status_snapshot()

    assert isinstance(result, MultiGraphStatusSnapshot)
    assert result.active_position == 1  # First graph active by default
    assert result.total_graphs == 2
    assert result.active_running_state == RunningState.RUNNING


def test_session_runtime_get_multi_graph_status_snapshot_returns_idle_when_empty() -> (
    None
):
    """Should return snapshot with idle state when no graphs exist."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    result = runtime.get_multi_graph_status_snapshot()

    assert isinstance(result, MultiGraphStatusSnapshot)
    assert result.active_position == 1
    assert result.total_graphs == 0
    assert result.active_running_state == RunningState.IDLE


def test_session_runtime_create_fork_request_from_current_node() -> None:
    """Should create ForkFromCurrentNodeRequest from active graph context."""
    runtime = SessionRuntime(session_graph=SessionGraph())
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
        is_active=True,
    )
    runtime.register_graph_session(session)

    result = runtime.create_fork_request(seed="custom-seed")

    assert isinstance(result, ForkFromCurrentNodeRequest)
    assert result.active_graph_id == "550e8400-e29b-41d4-a716-446655440000"
    assert result.current_node_id == "node-1"
    assert result.seed == "custom-seed"


def test_session_runtime_create_fork_request_returns_none_when_no_active_graph() -> (
    None
):
    """Should return None when no active graph exists for fork."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    result = runtime.create_fork_request(seed="custom-seed")

    assert result is None


def test_session_runtime_create_fork_request_returns_none_when_no_current_node() -> (
    None
):
    """Should return None when active graph has no current node."""
    runtime = SessionRuntime(session_graph=SessionGraph())
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id=None,  # No current node
        execution_status=ExecutionStatus.RUNNING,
        is_active=True,
    )
    runtime.register_graph_session(session)

    result = runtime.create_fork_request(seed="custom-seed")

    assert result is None


def test_session_runtime_create_graph_switch_request_next() -> None:
    """Should create GraphSwitchRequest for next graph navigation."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    session1 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    session2 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440002",
        current_node_id="node-2",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session1)
    runtime.register_graph_session(session2)

    result = runtime.create_graph_switch_request(GraphNavigationDirection.NEXT)

    assert isinstance(result, GraphSwitchRequest)
    assert result.target_graph_id == session2.graph_id
    assert result.direction == GraphNavigationDirection.NEXT
    assert result.preserve_current is True


def test_session_runtime_create_graph_switch_request_previous() -> None:
    """Should create GraphSwitchRequest for previous graph navigation."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    session1 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    session2 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440002",
        current_node_id="node-2",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session1)
    runtime.register_graph_session(session2)
    runtime.switch_to_next_graph()  # Make session2 active

    result = runtime.create_graph_switch_request(GraphNavigationDirection.PREVIOUS)

    assert isinstance(result, GraphSwitchRequest)
    assert result.target_graph_id == session1.graph_id
    assert result.direction == GraphNavigationDirection.PREVIOUS


def test_session_runtime_create_graph_switch_request_returns_none_when_single_graph() -> (
    None
):
    """Should return None when only one graph exists."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session)

    result = runtime.create_graph_switch_request(GraphNavigationDirection.NEXT)

    assert result is None


def test_session_runtime_create_graph_switch_request_returns_none_when_no_graphs() -> (
    None
):
    """Should return None when no graphs exist."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    result = runtime.create_graph_switch_request(GraphNavigationDirection.NEXT)

    assert result is None


def test_session_runtime_update_current_node_id_updates_active_graph() -> None:
    """Should update current_node_id for the active graph session."""
    runtime = SessionRuntime(session_graph=SessionGraph())
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session)

    runtime.update_current_node_id("new-node-id")

    active = runtime.get_active_graph_session()
    assert active is not None
    assert active.current_node_id == "new-node-id"


def test_session_runtime_update_current_node_id_returns_false_when_no_active_graph() -> (
    None
):
    """Should return False when no active graph to update."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    result = runtime.update_current_node_id("new-node-id")

    assert result is False


def test_session_runtime_update_current_node_id_returns_true_on_success() -> None:
    """Should return True when current_node_id is updated successfully."""
    runtime = SessionRuntime(session_graph=SessionGraph())
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session)

    result = runtime.update_current_node_id("new-node-id")

    assert result is True


def test_session_runtime_update_execution_status_updates_active_graph() -> None:
    """Should update execution_status for the active graph session."""
    runtime = SessionRuntime(session_graph=SessionGraph())
    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.IDLE,
    )
    runtime.register_graph_session(session)

    runtime.update_execution_status(ExecutionStatus.RUNNING)

    active = runtime.get_active_graph_session()
    assert active is not None
    assert active.execution_status == ExecutionStatus.RUNNING


def test_session_runtime_update_execution_status_returns_false_when_no_active_graph() -> (
    None
):
    """Should return False when no active graph to update."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    result = runtime.update_execution_status(ExecutionStatus.RUNNING)

    assert result is False


def test_session_runtime_graph_count_returns_number_of_graphs() -> None:
    """Should return the total number of registered graph sessions."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    assert runtime.graph_count == 0

    session = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        current_node_id="node-1",
        execution_status=ExecutionStatus.IDLE,
    )
    runtime.register_graph_session(session)

    assert runtime.graph_count == 1


def test_session_runtime_active_graph_index_returns_current_index() -> None:
    """Should return the current active graph index."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    assert runtime.active_graph_index == 0

    session1 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        current_node_id="node-1",
        execution_status=ExecutionStatus.RUNNING,
    )
    session2 = GraphSession(
        graph_id="550e8400-e29b-41d4-a716-446655440002",
        current_node_id="node-2",
        execution_status=ExecutionStatus.RUNNING,
    )
    runtime.register_graph_session(session1)
    runtime.register_graph_session(session2)

    assert runtime.active_graph_index == 0

    runtime.switch_to_next_graph()

    assert runtime.active_graph_index == 1
