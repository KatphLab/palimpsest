"""Contract tests for ForkFromCurrentNodeRequest per CA-003.

Validates that ForkFromCurrentNodeRequest:
- Contains active graph identifier (UUID)
- Contains current node identifier
- Contains user-provided seed value (optional)
- Enforces validation rules per contract
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from models.requests import ForkFromCurrentNodeRequest


class TestForkFromCurrentNodeRequestContract:
    """Contract validation for ForkFromCurrentNodeRequest per CA-003."""

    def test_request_contains_active_graph_id(self) -> None:
        """ForkFromCurrentNodeRequest MUST contain active graph identifier (UUID)."""

        graph_id = str(uuid4())
        node_id = "node-123"

        request = ForkFromCurrentNodeRequest(
            active_graph_id=graph_id,
            current_node_id=node_id,
        )

        assert request.active_graph_id == graph_id

    def test_request_contains_current_node_id(self) -> None:
        """ForkFromCurrentNodeRequest MUST contain current node identifier."""

        graph_id = str(uuid4())
        node_id = "current-node-abc"

        request = ForkFromCurrentNodeRequest(
            active_graph_id=graph_id,
            current_node_id=node_id,
        )

        assert request.current_node_id == node_id

    def test_request_contains_optional_seed(self) -> None:
        """ForkFromCurrentNodeRequest MUST support optional user-provided seed."""

        graph_id = str(uuid4())
        node_id = "node-456"
        seed = "my-custom-seed-text"

        request = ForkFromCurrentNodeRequest(
            active_graph_id=graph_id,
            current_node_id=node_id,
            seed=seed,
        )

        assert request.seed == seed

    def test_request_allows_null_seed_for_default_behavior(self) -> None:
        """ForkFromCurrentNodeRequest seed=null means default seed behavior."""

        graph_id = str(uuid4())
        node_id = "node-789"

        request = ForkFromCurrentNodeRequest(
            active_graph_id=graph_id,
            current_node_id=node_id,
            seed=None,
        )

        assert request.seed is None

    def test_request_validates_active_graph_id_is_valid_uuid(self) -> None:
        """ForkFromCurrentNodeRequest MUST validate active_graph_id is valid UUID."""

        invalid_graph_id = "not-a-valid-uuid"
        node_id = "node-123"

        with pytest.raises(ValidationError) as exc_info:
            ForkFromCurrentNodeRequest(
                active_graph_id=invalid_graph_id,
                current_node_id=node_id,
            )

        assert "active_graph_id" in str(exc_info.value)

    def test_request_validates_current_node_id_not_empty(self) -> None:
        """ForkFromCurrentNodeRequest MUST reject empty current_node_id."""

        graph_id = str(uuid4())

        with pytest.raises(ValidationError) as exc_info:
            ForkFromCurrentNodeRequest(
                active_graph_id=graph_id,
                current_node_id="",
            )

        assert "current_node_id" in str(exc_info.value)

    def test_request_validates_seed_max_length(self) -> None:
        """ForkFromCurrentNodeRequest seed MUST not exceed 255 characters."""

        graph_id = str(uuid4())
        node_id = "node-123"
        too_long_seed = "x" * 256

        with pytest.raises(ValidationError) as exc_info:
            ForkFromCurrentNodeRequest(
                active_graph_id=graph_id,
                current_node_id=node_id,
                seed=too_long_seed,
            )

        assert "seed" in str(exc_info.value)

    def test_request_validates_seed_not_whitespace_only(self) -> None:
        """ForkFromCurrentNodeRequest seed MUST be at least 1 character when provided."""

        graph_id = str(uuid4())
        node_id = "node-123"

        with pytest.raises(ValidationError) as exc_info:
            ForkFromCurrentNodeRequest(
                active_graph_id=graph_id,
                current_node_id=node_id,
                seed="   ",
            )

        assert "seed" in str(exc_info.value)

    def test_request_validates_seed_at_boundary_length(self) -> None:
        """ForkFromCurrentNodeRequest seed at exactly 255 chars is valid."""

        graph_id = str(uuid4())
        node_id = "node-123"
        boundary_seed = "x" * 255

        request = ForkFromCurrentNodeRequest(
            active_graph_id=graph_id,
            current_node_id=node_id,
            seed=boundary_seed,
        )

        assert request.seed == boundary_seed

    def test_request_accepts_whitespace_stripped_seed(self) -> None:
        """ForkFromCurrentNodeRequest strips whitespace from seed."""

        graph_id = str(uuid4())
        node_id = "node-123"
        seed_with_whitespace = "  my-seed-text  "

        request = ForkFromCurrentNodeRequest(
            active_graph_id=graph_id,
            current_node_id=node_id,
            seed=seed_with_whitespace,
        )

        assert request.seed == "my-seed-text"


class TestForkFromCurrentNodeRequestValidationRules:
    """Validation rules per contract spec for ForkFromCurrentNodeRequest."""

    def test_active_graph_id_must_be_non_empty(self) -> None:
        """active_graph_id field must not be empty string."""

        with pytest.raises(ValidationError) as exc_info:
            ForkFromCurrentNodeRequest(
                active_graph_id="",
                current_node_id="node-123",
            )

        assert "active_graph_id" in str(exc_info.value)

    def test_current_node_id_must_be_non_empty(self) -> None:
        """current_node_id field must not be empty string."""

        graph_id = str(uuid4())

        with pytest.raises(ValidationError) as exc_info:
            ForkFromCurrentNodeRequest(
                active_graph_id=graph_id,
                current_node_id="",
            )

        assert "current_node_id" in str(exc_info.value)

    def test_minimal_valid_request_has_graph_id_and_node_id(self) -> None:
        """Minimal valid request requires only active_graph_id and current_node_id."""

        graph_id = str(uuid4())
        node_id = "minimal-node"

        request = ForkFromCurrentNodeRequest(
            active_graph_id=graph_id,
            current_node_id=node_id,
        )

        assert request.active_graph_id == graph_id
        assert request.current_node_id == node_id
        assert request.seed is None
