"""Tests for session runtime active graph context integration with multi-graph system."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.common import SessionStatus
from models.execution import ExecutionStatus
from models.graph_session import GraphSession
from models.requests import (
    ForkFromCurrentNodeRequest,
    GraphNavigationDirection,
    GraphSwitchRequest,
)
from models.responses import MultiGraphStatusSnapshot, RunningState
from runtime.event_log import EventLog
from runtime.graph_registry import GraphRegistry
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider


def _build_runtime_with_two_switchable_graphs() -> tuple[
    SessionRuntime, UUID, UUID, SessionGraph
]:
    """Create runtime state with two registered graph/session contexts."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    runtime._scene_agent._provider = DeterministicSceneGenerationProvider()
    start = StartSessionCommand(
        command_id="cmd-start-for-switch-sync",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A station clock that skips backward"),
    )
    result = runtime.handle_command(start)
    assert result.session_id is not None

    first_session_id = result.session_id
    first_state = runtime._session_states[first_session_id]
    second_session_id = uuid4()
    second_graph = SessionGraph()
    runtime._session_states[second_session_id] = first_state.model_copy(
        deep=True,
        update={
            "session": first_state.session.model_copy(
                deep=True,
                update={
                    "session_id": second_session_id,
                    "parent_session_id": first_session_id,
                },
            ),
            "session_graph": second_graph,
            "event_log": EventLog(
                session_id=second_session_id,
                latest_sequence=0,
                events=[],
            ),
        },
    )

    runtime.register_graph_session(
        GraphSession(
            graph_id=str(second_session_id),
            current_node_id=None,
            execution_status=ExecutionStatus.IDLE,
        )
    )
    runtime.activate_session(first_session_id)
    runtime.graph_registry.set_active_session(str(first_session_id))
    return runtime, first_session_id, second_session_id, second_graph


def test_session_runtime_initializes_with_empty_graph_registry() -> None:
    """Runtime should initialize with an empty graph registry for multi-graph management."""
    runtime = SessionRuntime(session_graph=SessionGraph())

    # Should have a graph_registry attribute
    assert hasattr(runtime, "graph_registry")
    # Should be a GraphRegistry instance
    assert isinstance(runtime.graph_registry, GraphRegistry)
    # Should start empty
    assert runtime.graph_registry.get_session_count() == 0


def test_start_session_registers_root_graph_session_with_current_node() -> None:
    """Starting a session should create a GraphSession for forking context."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    runtime._scene_agent._provider = DeterministicSceneGenerationProvider()
    command = StartSessionCommand(
        command_id="cmd-start-root-graph",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A lighthouse in the fog"),
    )

    result = runtime.handle_command(command)

    assert result.accepted is True
    assert result.session_id is not None
    assert runtime.graph_count == 1

    active_graph = runtime.get_active_graph_session()
    assert active_graph is not None
    assert active_graph.graph_id == str(result.session_id)
    assert active_graph.current_node_id is not None


def test_run_mutation_cycle_syncs_graph_session_current_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation cycles should keep GraphSession.current_node_id in sync."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    runtime._scene_agent._provider = DeterministicSceneGenerationProvider()
    start = StartSessionCommand(
        command_id="cmd-start-sync",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="A city under glass"),
    )
    runtime.handle_command(start)
    assert runtime.session is not None
    runtime.session.status = SessionStatus.RUNNING

    new_current_node_id = "node-scene-synced"

    def fake_mutation_cycle() -> None:
        assert runtime.session is not None
        runtime.session.active_node_ids.append(new_current_node_id)
        return None

    monkeypatch.setattr(runtime, "_run_mutation_cycle_locked", fake_mutation_cycle)

    runtime.run_mutation_cycle()

    active_graph = runtime.get_active_graph_session()
    assert active_graph is not None
    assert active_graph.current_node_id == new_current_node_id


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
    runtime, _, second_session_id, _ = _build_runtime_with_two_switchable_graphs()

    # Switch to next
    result = runtime.switch_to_next_graph()

    assert result.graph_id == str(second_session_id)
    assert result.is_active is True
    # Verify the active session changed in registry
    active = runtime.get_active_graph_session()
    assert active is not None
    assert active.graph_id == str(second_session_id)


def test_session_runtime_switch_to_previous_graph_updates_active() -> None:
    """Should switch to previous graph and update active context."""
    runtime, first_session_id, _, _ = _build_runtime_with_two_switchable_graphs()
    # Switch to next first to make session2 active
    runtime.switch_to_next_graph()

    # Switch to previous
    result = runtime.switch_to_previous_graph()

    assert result.graph_id == str(first_session_id)
    assert result.is_active is True


def test_session_runtime_switch_to_next_graph_requires_runtime_state() -> None:
    """Switching should fail when active graph has no runtime session state."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    runtime.register_graph_session(
        GraphSession(
            graph_id="550e8400-e29b-41d4-a716-446655440001",
            current_node_id="node-1",
            execution_status=ExecutionStatus.RUNNING,
        )
    )
    runtime.register_graph_session(
        GraphSession(
            graph_id="550e8400-e29b-41d4-a716-446655440002",
            current_node_id="node-2",
            execution_status=ExecutionStatus.RUNNING,
        )
    )

    with pytest.raises(ValueError, match="unknown session"):
        runtime.switch_to_next_graph()


def test_session_runtime_switch_to_next_graph_syncs_runtime_context() -> None:
    """Switching next graph should activate matching runtime session state."""

    runtime, first_session_id, second_session_id, second_graph = (
        _build_runtime_with_two_switchable_graphs()
    )
    assert runtime.session_id == first_session_id

    runtime.switch_to_next_graph()

    assert runtime.session_id == second_session_id
    assert runtime.session is not None
    assert runtime.session.session_id == second_session_id
    assert runtime.session_graph is second_graph


def test_session_runtime_switch_to_next_graph_switches_event_log_context() -> None:
    """Switching next graph should switch to that graph's event log."""

    runtime, _, second_session_id, _ = _build_runtime_with_two_switchable_graphs()

    runtime.switch_to_next_graph()

    assert runtime.event_log is not None
    assert runtime.event_log.session_id == second_session_id


def test_session_runtime_switch_to_previous_graph_syncs_runtime_context() -> None:
    """Switching previous graph should restore the prior runtime session state."""

    runtime, first_session_id, second_session_id, _ = (
        _build_runtime_with_two_switchable_graphs()
    )
    runtime.switch_to_next_graph()
    assert runtime.session_id == second_session_id

    runtime.switch_to_previous_graph()

    assert runtime.session_id == first_session_id
    assert runtime.session is not None
    assert runtime.session.session_id == first_session_id


def test_session_runtime_switch_to_previous_graph_switches_event_log_context() -> None:
    """Switching previous graph should restore the prior graph event log."""

    runtime, first_session_id, _, _ = _build_runtime_with_two_switchable_graphs()
    runtime.switch_to_next_graph()

    runtime.switch_to_previous_graph()

    assert runtime.event_log is not None
    assert runtime.event_log.session_id == first_session_id


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
    runtime, first_session_id, _, _ = _build_runtime_with_two_switchable_graphs()
    runtime.switch_to_next_graph()  # Make session2 active

    result = runtime.create_graph_switch_request(GraphNavigationDirection.PREVIOUS)

    assert isinstance(result, GraphSwitchRequest)
    assert result.target_graph_id == str(first_session_id)
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
    runtime, _, _, _ = _build_runtime_with_two_switchable_graphs()

    assert runtime.active_graph_index == 0

    runtime.switch_to_next_graph()

    assert runtime.active_graph_index == 1
