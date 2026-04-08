"""Tests for multi-graph view model entities."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.multi_graph_view import GraphSummary


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
