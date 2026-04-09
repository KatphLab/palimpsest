"""Tests for multi-graph view model entities."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.multi_graph_view import (
    GraphListView,
    GraphPosition,
    GraphSummary,
    MultiGraphViewState,
)


def test_graph_summary_accepts_contract_aliases() -> None:
    """GraphSummary should deserialize camelCase contract field names."""

    summary = GraphSummary.model_validate(
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Primary branch",
            "node_count": 12,
            "edge_count": 16,
            "created_at": datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
            "fork_source": "550e8400-e29b-41d4-a716-446655440001",
            "current_state": "A tense negotiation unfolds.",
            "last_modified": datetime(2026, 4, 8, 10, 5, tzinfo=timezone.utc),
            "labels": ["draft", "hero-path"],
        }
    )

    assert summary.node_count == 12
    assert summary.edge_count == 16


def test_graph_summary_accepts_valid_data() -> None:
    """Graph summaries should validate contract-compliant fields."""

    summary = GraphSummary(
        id="550e8400-e29b-41d4-a716-446655440000",
        name="Primary branch",
        node_count=12,
        edge_count=16,
        created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        fork_source="550e8400-e29b-41d4-a716-446655440001",
        current_state="A tense negotiation unfolds.",
        last_modified=datetime(2026, 4, 8, 10, 5, tzinfo=timezone.utc),
        labels=["draft", "hero-path"],
    )

    assert summary.node_count == 12
    assert summary.edge_count == 16
    assert summary.labels == ["draft", "hero-path"]


def test_graph_summary_rejects_invalid_fork_source_uuid() -> None:
    """Fork source should enforce the lowercase canonical UUID pattern."""

    with pytest.raises(ValidationError):
        GraphSummary(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Primary branch",
            node_count=12,
            edge_count=16,
            created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
            fork_source="NOT-A-UUID",
            current_state="A tense negotiation unfolds.",
            last_modified=datetime(2026, 4, 8, 10, 5, tzinfo=timezone.utc),
        )


def test_graph_summary_rejects_negative_counts() -> None:
    """Node and edge counts should never be negative."""

    with pytest.raises(ValidationError):
        GraphSummary(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Primary branch",
            node_count=-1,
            edge_count=16,
            created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
            current_state="A tense negotiation unfolds.",
            last_modified=datetime(2026, 4, 8, 10, 5, tzinfo=timezone.utc),
        )


class TestGraphPosition:
    """Tests for GraphPosition entity."""

    def test_graph_position_accepts_valid_data(self) -> None:
        """GraphPosition should accept valid graph ID and position."""
        position = GraphPosition(
            graph_id="550e8400-e29b-41d4-a716-446655440000",
            position=1,
            is_active=True,
        )

        assert position.graph_id == "550e8400-e29b-41d4-a716-446655440000"
        assert position.position == 1
        assert position.is_active is True

    def test_graph_position_defaults(self) -> None:
        """GraphPosition should have sensible defaults."""
        position = GraphPosition(
            graph_id="550e8400-e29b-41d4-a716-446655440000",
            position=1,
        )

        assert position.is_active is False

    def test_graph_position_rejects_invalid_uuid(self) -> None:
        """GraphPosition should reject non-UUID graph_id."""
        with pytest.raises(ValidationError) as exc_info:
            GraphPosition(
                graph_id="not-a-uuid",
                position=1,
            )

        assert "graph_id" in str(exc_info.value)

    def test_graph_position_rejects_position_less_than_one(self) -> None:
        """GraphPosition should reject position less than 1."""
        with pytest.raises(ValidationError) as exc_info:
            GraphPosition(
                graph_id="550e8400-e29b-41d4-a716-446655440000",
                position=0,
            )

        assert "position" in str(exc_info.value)


class TestGraphListView:
    """Tests for GraphListView entity."""

    def test_graph_list_view_accepts_valid_data(self) -> None:
        """GraphListView should accept valid graph positions."""
        list_view = GraphListView(
            graphs=[
                GraphPosition(
                    graph_id="550e8400-e29b-41d4-a716-446655440000",
                    position=1,
                    is_active=True,
                ),
                GraphPosition(
                    graph_id="550e8400-e29b-41d4-a716-446655440001",
                    position=2,
                    is_active=False,
                ),
            ],
            active_index=0,
            total_count=2,
        )

        assert len(list_view.graphs) == 2
        assert list_view.active_index == 0
        assert list_view.total_count == 2

    def test_graph_list_view_defaults(self) -> None:
        """GraphListView should have sensible defaults."""
        list_view = GraphListView()

        assert list_view.graphs == []
        assert list_view.active_index == 0
        assert list_view.total_count == 0

    def test_graph_list_view_rejects_non_sequential_positions(self) -> None:
        """GraphListView should reject non-sequential positions."""
        with pytest.raises(ValidationError) as exc_info:
            GraphListView(
                graphs=[
                    GraphPosition(
                        graph_id="550e8400-e29b-41d4-a716-446655440000",
                        position=1,
                    ),
                    GraphPosition(
                        graph_id="550e8400-e29b-41d4-a716-446655440001",
                        position=3,  # Skips position 2
                    ),
                ],
            )

        assert "graph positions must be sequential" in str(exc_info.value)

    def test_graph_list_view_rejects_duplicate_graph_ids(self) -> None:
        """GraphListView should reject duplicate graph_ids."""
        with pytest.raises(ValidationError) as exc_info:
            GraphListView(
                graphs=[
                    GraphPosition(
                        graph_id="550e8400-e29b-41d4-a716-446655440000",
                        position=1,
                    ),
                    GraphPosition(
                        graph_id="550e8400-e29b-41d4-a716-446655440000",  # Duplicate
                        position=2,
                    ),
                ],
            )

        assert "graph_ids must be unique" in str(exc_info.value)

    def test_graph_list_view_accepts_empty_list(self) -> None:
        """GraphListView should accept empty graphs list."""
        list_view = GraphListView(graphs=[])

        assert list_view.graphs == []
        assert list_view.total_count == 0


class TestMultiGraphViewState:
    """Tests for MultiGraphViewState entity."""

    def test_multi_graph_view_state_accepts_valid_data(self) -> None:
        """MultiGraphViewState should accept valid view state."""
        graph_id = "550e8400-e29b-41d4-a716-446655440000"
        view_state = MultiGraphViewState(
            graph_list=GraphListView(
                graphs=[
                    GraphPosition(
                        graph_id=graph_id,
                        position=1,
                        is_active=True,
                    ),
                ],
                active_index=0,
                total_count=1,
            ),
            summaries=[],  # Empty is allowed
            active_graph_id=graph_id,
        )

        assert view_state.active_graph_id == graph_id
        assert len(view_state.graph_list.graphs) == 1

    def test_multi_graph_view_state_accepts_null_active_graph_id(self) -> None:
        """MultiGraphViewState should allow null active_graph_id."""
        view_state = MultiGraphViewState(
            graph_list=GraphListView(graphs=[]),
            active_graph_id=None,
        )

        assert view_state.active_graph_id is None

    def test_multi_graph_view_state_rejects_invalid_active_graph_id(self) -> None:
        """MultiGraphViewState should reject non-UUID active_graph_id."""
        with pytest.raises(ValidationError) as exc_info:
            MultiGraphViewState(
                graph_list=GraphListView(graphs=[]),
                active_graph_id="not-a-uuid",
            )

        assert "active_graph_id" in str(exc_info.value)

    def test_multi_graph_view_state_allows_empty_summaries(self) -> None:
        """MultiGraphViewState should allow empty summaries list."""
        view_state = MultiGraphViewState(
            graph_list=GraphListView(
                graphs=[
                    GraphPosition(
                        graph_id="550e8400-e29b-41d4-a716-446655440000",
                        position=1,
                    ),
                ],
            ),
            summaries=[],  # Empty should be allowed
        )

        assert view_state.summaries == []
