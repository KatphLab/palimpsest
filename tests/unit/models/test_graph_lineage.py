"""Tests for the GraphLineage model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.graph_lineage import GraphLineage


def test_graph_lineage_accepts_valid_relationship() -> None:
    """Lineage records should validate parent-child relationships."""

    lineage = GraphLineage(
        parent_graph_id="550e8400-e29b-41d4-a716-446655440000",
        child_graph_id="550e8400-e29b-41d4-a716-446655440001",
        depth=1,
        branch_id="main-left",
    )

    assert lineage.depth == 1
    assert lineage.branch_id == "main-left"


def test_graph_lineage_rejects_negative_depth() -> None:
    """Depth values must be non-negative integers."""

    with pytest.raises(ValidationError):
        GraphLineage(
            parent_graph_id="550e8400-e29b-41d4-a716-446655440000",
            child_graph_id="550e8400-e29b-41d4-a716-446655440001",
            depth=-1,
            branch_id="main-left",
        )


def test_graph_lineage_rejects_self_references() -> None:
    """Lineage records should not allow parent and child IDs to match."""

    with pytest.raises(ValidationError):
        GraphLineage(
            parent_graph_id="550e8400-e29b-41d4-a716-446655440000",
            child_graph_id="550e8400-e29b-41d4-a716-446655440000",
            depth=1,
            branch_id="main-left",
        )
