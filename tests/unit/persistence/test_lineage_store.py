"""Tests for LineageStore ancestry tracking behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from models.graph_lineage import GraphLineage
from persistence.lineage_store import LineageStore


def _lineage(
    parent_graph_id: str,
    child_graph_id: str,
    *,
    depth: int,
    branch_id: str,
) -> GraphLineage:
    return GraphLineage(
        parent_graph_id=parent_graph_id,
        child_graph_id=child_graph_id,
        depth=depth,
        branch_id=branch_id,
    )


def test_lineage_store_tracks_parent_and_children(tmp_path: Path) -> None:
    """Lineage store should provide direct parent/child lookups."""

    store = LineageStore(root_dir=tmp_path)
    store.add_lineage(
        _lineage(
            "550e8400-e29b-41d4-a716-446655440000",
            "550e8400-e29b-41d4-a716-446655440001",
            depth=1,
            branch_id="main-left",
        )
    )

    assert (
        store.get_parent("550e8400-e29b-41d4-a716-446655440001")
        == "550e8400-e29b-41d4-a716-446655440000"
    )
    assert store.get_children("550e8400-e29b-41d4-a716-446655440000") == [
        "550e8400-e29b-41d4-a716-446655440001"
    ]


def test_lineage_store_get_ancestry_returns_root_to_leaf_path(tmp_path: Path) -> None:
    """Ancestry should include all lineage links from root to target graph."""

    store = LineageStore(root_dir=tmp_path)
    store.add_lineage(
        _lineage(
            "550e8400-e29b-41d4-a716-446655440000",
            "550e8400-e29b-41d4-a716-446655440001",
            depth=1,
            branch_id="main-left",
        )
    )
    store.add_lineage(
        _lineage(
            "550e8400-e29b-41d4-a716-446655440001",
            "550e8400-e29b-41d4-a716-446655440002",
            depth=2,
            branch_id="main-left-left",
        )
    )

    ancestry = store.get_ancestry("550e8400-e29b-41d4-a716-446655440002")

    assert [item.parent_graph_id for item in ancestry] == [
        "550e8400-e29b-41d4-a716-446655440000",
        "550e8400-e29b-41d4-a716-446655440001",
    ]
    assert [item.child_graph_id for item in ancestry] == [
        "550e8400-e29b-41d4-a716-446655440001",
        "550e8400-e29b-41d4-a716-446655440002",
    ]


def test_lineage_store_rejects_duplicate_relationships(tmp_path: Path) -> None:
    """Adding the same parent-child relationship twice should fail."""

    store = LineageStore(root_dir=tmp_path)
    lineage = _lineage(
        "550e8400-e29b-41d4-a716-446655440000",
        "550e8400-e29b-41d4-a716-446655440001",
        depth=1,
        branch_id="main-left",
    )
    store.add_lineage(lineage)

    with pytest.raises(ValueError, match="already exists"):
        store.add_lineage(lineage)
