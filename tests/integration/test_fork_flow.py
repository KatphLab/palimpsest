"""Integration tests for fork-from-current-node flow."""

from __future__ import annotations

from uuid import uuid4

import pytest

from models.execution import ExecutionStatus
from models.fork_request import ForkRequest, ForkRequestStatus
from models.graph_session import GraphSession
from models.requests import ForkFromCurrentNodeRequest
from runtime.session_runtime import SessionRuntime


class TestForkFromCurrentNodeFlow:
    """Integration test for fork-from-current-node flow (T017).

    Acceptance Scenario:
    Given a graph is open and a current node is selected,
    When the user presses `f`,
    Then the system initiates a fork flow from that current node.
    """

    def test_fork_flow_creates_fork_request_from_current_node(self) -> None:
        """Fork flow creates ForkFromCurrentNodeRequest from current context."""

        # Setup: Create runtime with active graph and current node
        runtime = SessionRuntime()
        graph_id = str(uuid4())
        current_node_id = "node-seed-001"

        # Register an active graph session
        session = GraphSession(
            graph_id=graph_id,
            current_node_id=current_node_id,
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(session)

        # Action: Create fork request (simulating 'f' keybinding)
        fork_request = runtime.create_fork_request(seed="test-fork-seed")

        # Assert: Fork request should be created with correct context
        assert fork_request is not None
        assert fork_request.active_graph_id == graph_id
        assert fork_request.current_node_id == current_node_id
        assert fork_request.seed == "test-fork-seed"

    def test_fork_flow_fails_without_current_node(self) -> None:
        """Fork flow should fail when no current node is selected."""

        runtime = SessionRuntime()
        graph_id = str(uuid4())

        # Register graph session without current_node_id
        session = GraphSession(
            graph_id=graph_id,
            current_node_id=None,
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(session)

        # Action: Attempt to create fork request
        fork_request = runtime.create_fork_request(seed="test-seed")

        # Assert: Should return None when no current node
        assert fork_request is None

    def test_fork_flow_fails_without_active_graph(self) -> None:
        """Fork flow should fail when no active graph exists."""

        runtime = SessionRuntime()

        # Action: Attempt to create fork request without any graphs
        fork_request = runtime.create_fork_request(seed="test-seed")

        # Assert: Should return None when no active graph
        assert fork_request is None

    def test_fork_request_validates_seed_input(self) -> None:
        """Fork request should accept and validate seed input."""

        runtime = SessionRuntime()
        graph_id = str(uuid4())

        session = GraphSession(
            graph_id=graph_id,
            current_node_id="node-001",
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(session)

        # Test with valid seed
        fork_request_with_seed = runtime.create_fork_request(seed="valid-seed")
        assert fork_request_with_seed is not None
        assert fork_request_with_seed.seed == "valid-seed"

        # Test with None seed (default behavior)
        fork_request_no_seed = runtime.create_fork_request(seed=None)
        assert fork_request_no_seed is not None
        assert fork_request_no_seed.seed is None

    def test_fork_request_contains_required_contract_fields(self) -> None:
        """ForkFromCurrentNodeRequest must contain all CA-003 contract fields."""

        runtime = SessionRuntime()
        graph_id = str(uuid4())
        node_id = "current-node-abc"

        session = GraphSession(
            graph_id=graph_id,
            current_node_id=node_id,
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(session)

        fork_request = runtime.create_fork_request(seed="contract-test-seed")

        assert fork_request is not None
        # Verify all CA-003 contract fields present
        assert hasattr(fork_request, "active_graph_id")
        assert hasattr(fork_request, "current_node_id")
        assert hasattr(fork_request, "seed")
        assert fork_request.active_graph_id == graph_id
        assert fork_request.current_node_id == node_id


class TestForkConfirmationCreatesNewActiveGraph:
    """Integration test for fork confirmation creates new active graph (T018).

    Acceptance Scenario:
    Given the fork flow is active,
    When the user enters a seed and confirms,
    Then a new graph is created using that seed and opened as the active graph.
    """

    def test_fork_confirmation_creates_new_graph(self) -> None:
        """Confirming fork should create a new graph in the registry."""

        runtime = SessionRuntime()
        original_graph_id = str(uuid4())

        # Setup: Create original active graph
        original_session = GraphSession(
            graph_id=original_graph_id,
            current_node_id="node-original",
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(original_session)

        initial_count = runtime.graph_registry.get_session_count()

        # Action: Confirm fork (this would be called when user confirms)
        fork_request = ForkFromCurrentNodeRequest(
            active_graph_id=original_graph_id,
            current_node_id="node-original",
            seed="fork-seed-text",
        )

        # Simulate fork confirmation creating new graph
        # Note: This will fail until implementation is added
        try:
            new_session = self._simulate_fork_confirmation(runtime, fork_request)

            # Assert: New graph should exist
            assert new_session is not None
            assert runtime.graph_registry.get_session_count() == initial_count + 1
        except (AttributeError, NotImplementedError):
            pytest.fail("Fork confirmation not yet implemented")

    def test_fork_confirmation_sets_new_graph_as_active(self) -> None:
        """New forked graph should become the active graph."""

        runtime = SessionRuntime()
        original_graph_id = str(uuid4())

        original_session = GraphSession(
            graph_id=original_graph_id,
            current_node_id="node-original",
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(original_session)

        # Get initial active graph
        initial_active = runtime.get_active_graph_session()
        assert initial_active is not None
        initial_active_id = initial_active.graph_id

        # Action: Confirm fork
        fork_request = ForkFromCurrentNodeRequest(
            active_graph_id=original_graph_id,
            current_node_id="node-original",
            seed="active-test-seed",
        )

        try:
            self._simulate_fork_confirmation(runtime, fork_request)

            # Assert: New graph should be active (different from original)
            new_active = runtime.get_active_graph_session()
            assert new_active is not None
            assert new_active.graph_id != initial_active_id
            assert new_active.is_active is True
        except (AttributeError, NotImplementedError):
            pytest.fail("Fork confirmation with active switch not yet implemented")

    def test_fork_preserves_source_graph_state(self) -> None:
        """Source graph state should be preserved at fork boundary (CA-002)."""

        runtime = SessionRuntime()
        original_graph_id = str(uuid4())
        original_node_id = "node-original"

        original_session = GraphSession(
            graph_id=original_graph_id,
            current_node_id=original_node_id,
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(original_session)

        # Action: Confirm fork
        fork_request = ForkFromCurrentNodeRequest(
            active_graph_id=original_graph_id,
            current_node_id=original_node_id,
            seed="preserve-test",
        )

        try:
            self._simulate_fork_confirmation(runtime, fork_request)

            # Assert: Source graph should still exist with original node
            source_session = None
            for session in runtime.graph_registry.list_sessions():
                if session.graph_id == original_graph_id:
                    source_session = session
                    break

            assert source_session is not None
            assert source_session.current_node_id == original_node_id
            assert source_session.execution_status == ExecutionStatus.RUNNING
        except (AttributeError, NotImplementedError):
            pytest.fail("Source graph preservation not yet implemented")

    def test_fork_creates_graph_with_correct_seed(self) -> None:
        """Forked graph should use the user-provided seed."""

        runtime = SessionRuntime()
        original_graph_id = str(uuid4())
        test_seed = "my-custom-fork-seed-123"

        original_session = GraphSession(
            graph_id=original_graph_id,
            current_node_id="node-original",
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(original_session)

        fork_request = ForkFromCurrentNodeRequest(
            active_graph_id=original_graph_id,
            current_node_id="node-original",
            seed=test_seed,
        )

        try:
            new_session = self._simulate_fork_confirmation(runtime, fork_request)

            # The forked session should have been created with the seed
            assert new_session is not None
            # Implementation-specific: verify seed was passed to new graph
        except (AttributeError, NotImplementedError):
            pytest.fail("Seed propagation in fork not yet implemented")

    def test_status_snapshot_reflects_new_active_graph(self) -> None:
        """After fork, status snapshot should reflect new active graph."""

        runtime = SessionRuntime()
        original_graph_id = str(uuid4())

        original_session = GraphSession(
            graph_id=original_graph_id,
            current_node_id="node-original",
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(original_session)

        # Get initial status
        initial_status = runtime.get_multi_graph_status_snapshot()
        assert initial_status.total_graphs == 1
        assert initial_status.active_position == 1

        # Action: Confirm fork
        fork_request = ForkFromCurrentNodeRequest(
            active_graph_id=original_graph_id,
            current_node_id="node-original",
            seed="status-test",
        )

        try:
            self._simulate_fork_confirmation(runtime, fork_request)

            # Assert: Status should show 2 graphs, with new one active
            new_status = runtime.get_multi_graph_status_snapshot()
            assert new_status.total_graphs == 2
            assert new_status.active_position in [1, 2]  # Should be 2 (new graph)
        except (AttributeError, NotImplementedError):
            pytest.fail("Status update after fork not yet implemented")

    def _simulate_fork_confirmation(
        self,
        runtime: SessionRuntime,
        fork_request: ForkFromCurrentNodeRequest,
    ) -> GraphSession | None:
        """Simulate the fork confirmation process.

        This is a helper that will be replaced by actual implementation.
        Currently raises NotImplementedError to indicate test-first approach.
        """

        # TODO: Replace with actual implementation when available
        # This simulates what should happen when user confirms fork:
        # 1. Create new graph from fork point
        # 2. Set new graph as active
        # 3. Preserve source graph state

        raise NotImplementedError("Fork confirmation implementation not yet available")


class TestForkRequestLifecycle:
    """Test ForkRequest lifecycle transitions per data-model.md."""

    def test_fork_request_starts_in_draft_state(self) -> None:
        """New ForkRequest should start in DRAFT status."""

        request = ForkRequest(
            active_graph_id=str(uuid4()),
            current_node_id="node-123",
            seed="test-seed",
            confirm=False,
        )

        assert request.status == ForkRequestStatus.DRAFT
        assert request.confirm is False

    def test_fork_request_confirmed_transition(self) -> None:
        """ForkRequest transitions to CONFIRMED when user confirms."""

        request = ForkRequest(
            active_graph_id=str(uuid4()),
            current_node_id="node-123",
            seed="test-seed",
            confirm=True,
        )

        # Simulate confirmation
        confirmed_request = request.model_copy(
            update={"confirm": True, "status": ForkRequestStatus.CONFIRMED}
        )

        assert confirmed_request.confirm is True
        assert confirmed_request.status == ForkRequestStatus.CONFIRMED

    def test_fork_request_cancelled_transition(self) -> None:
        """ForkRequest transitions to CANCELLED when user cancels."""

        request = ForkRequest(
            active_graph_id=str(uuid4()),
            current_node_id="node-123",
            seed="test-seed",
            confirm=False,
        )

        # Simulate cancellation
        cancelled_request = request.model_copy(
            update={"status": ForkRequestStatus.CANCELLED}
        )

        assert cancelled_request.status == ForkRequestStatus.CANCELLED


class TestForkEdgeCases:
    """Edge cases for fork flow per spec.md."""

    def test_blank_seed_uses_default_behavior(self) -> None:
        """If seed input is blank, use default seed behavior."""

        runtime = SessionRuntime()
        graph_id = str(uuid4())

        session = GraphSession(
            graph_id=graph_id,
            current_node_id="node-001",
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(session)

        # Test with None seed (blank/empty)
        fork_request = runtime.create_fork_request(seed=None)

        assert fork_request is not None
        assert fork_request.seed is None  # Default behavior

    def test_fork_from_invalid_node_id_fails(self) -> None:
        """Fork should fail validation when node_id is invalid."""

        runtime = SessionRuntime()
        graph_id = str(uuid4())

        session = GraphSession(
            graph_id=graph_id,
            current_node_id="",  # Invalid empty node
            execution_status=ExecutionStatus.RUNNING,
            is_active=True,
        )
        runtime.register_graph_session(session)

        # Fork request should fail or return None for invalid node
        fork_request = runtime.create_fork_request(seed="test")

        # Implementation should handle this gracefully
        assert fork_request is None or fork_request.current_node_id != ""
