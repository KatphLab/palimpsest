"""Tests for the ForkPoint model."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.fork_point import ForkPoint


def test_fork_point_accepts_valid_data() -> None:
    """Fork points should validate valid identifiers and metadata."""

    fork_point = ForkPoint(
        source_graph_id="550e8400-e29b-41d4-a716-446655440000",
        fork_edge_id="edge-42",
        timestamp=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        label="Hero turns left",
    )

    assert fork_point.source_graph_id == "550e8400-e29b-41d4-a716-446655440000"
    assert fork_point.fork_edge_id == "edge-42"
    assert fork_point.label == "Hero turns left"


def test_fork_point_rejects_invalid_source_graph_id() -> None:
    """Fork points should reject non-contract UUID values."""

    with pytest.raises(ValidationError):
        ForkPoint(
            source_graph_id="bad-id",
            fork_edge_id="edge-42",
            timestamp=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        )


def test_fork_point_rejects_blank_edge_id() -> None:
    """Fork points should require a non-empty edge identifier."""

    with pytest.raises(ValidationError):
        ForkPoint(
            source_graph_id="550e8400-e29b-41d4-a716-446655440000",
            fork_edge_id=" ",
            timestamp=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        )
