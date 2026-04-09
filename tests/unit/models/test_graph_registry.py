"""Tests for the GraphRegistry model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.graph_registry import GraphRegistry


class TestGraphRegistry:
    """Tests for GraphRegistry entity."""

    def test_graph_registry_accepts_valid_data(self) -> None:
        """GraphRegistry should accept valid ordered graph IDs."""
        registry = GraphRegistry(
            graph_ids=[
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440001",
                "550e8400-e29b-41d4-a716-446655440002",
            ],
            active_index=1,
        )

        assert len(registry.graph_ids) == 3
        assert registry.active_index == 1
        assert registry.total_graphs == 3
        assert registry.active_graph_id == "550e8400-e29b-41d4-a716-446655440001"

    def test_graph_registry_defaults(self) -> None:
        """GraphRegistry should have sensible defaults."""
        registry = GraphRegistry()

        assert registry.graph_ids == []
        assert registry.active_index == 0
        assert registry.total_graphs == 0
        assert registry.active_graph_id is None

    def test_graph_registry_rejects_invalid_uuid_in_list(self) -> None:
        """GraphRegistry should reject non-UUID in graph_ids."""
        with pytest.raises(ValidationError) as exc_info:
            GraphRegistry(
                graph_ids=[
                    "550e8400-e29b-41d4-a716-446655440000",
                    "not-a-uuid",
                ],
            )

        assert "graph_ids" in str(exc_info.value)

    def test_graph_registry_rejects_active_index_out_of_bounds(self) -> None:
        """GraphRegistry should reject active_index beyond graph count."""
        with pytest.raises(ValidationError) as exc_info:
            GraphRegistry(
                graph_ids=["550e8400-e29b-41d4-a716-446655440000"],
                active_index=5,
            )

        assert "active_index" in str(exc_info.value)

    def test_graph_registry_allows_active_index_with_empty_list(self) -> None:
        """GraphRegistry should allow active_index=0 when no graphs."""
        registry = GraphRegistry(graph_ids=[], active_index=0)

        assert registry.total_graphs == 0
        assert registry.active_graph_id is None

    def test_get_next_index_cycles_forward(self) -> None:
        """get_next_index should cycle to next graph."""
        registry = GraphRegistry(
            graph_ids=[
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440001",
                "550e8400-e29b-41d4-a716-446655440002",
            ],
            active_index=0,
        )

        assert registry.get_next_index() == 1

    def test_get_next_index_wraps_at_end(self) -> None:
        """get_next_index should wrap to start at end of list."""
        registry = GraphRegistry(
            graph_ids=[
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440001",
            ],
            active_index=1,
        )

        assert registry.get_next_index() == 0

    def test_get_previous_index_cycles_backward(self) -> None:
        """get_previous_index should cycle to previous graph."""
        registry = GraphRegistry(
            graph_ids=[
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440001",
                "550e8400-e29b-41d4-a716-446655440002",
            ],
            active_index=2,
        )

        assert registry.get_previous_index() == 1

    def test_get_previous_index_wraps_at_start(self) -> None:
        """get_previous_index should wrap to end at start of list."""
        registry = GraphRegistry(
            graph_ids=[
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440001",
            ],
            active_index=0,
        )

        assert registry.get_previous_index() == 1

    def test_navigation_methods_with_empty_list(self) -> None:
        """Navigation methods should return current index when no graphs."""
        registry = GraphRegistry(graph_ids=[], active_index=0)

        assert registry.get_next_index() == 0
        assert registry.get_previous_index() == 0

    def test_navigation_methods_with_single_graph(self) -> None:
        """Navigation methods should stay on same index with single graph."""
        registry = GraphRegistry(
            graph_ids=["550e8400-e29b-41d4-a716-446655440000"],
            active_index=0,
        )

        assert registry.get_next_index() == 0
        assert registry.get_previous_index() == 0
