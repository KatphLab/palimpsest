"""Tests for GraphStore persistence behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from models.graph_instance import GraphInstance
from persistence.graph_store import GraphStore
from tests.fixtures import build_graph_instance


def _build_graph_instance(graph_id: str) -> GraphInstance:
    return build_graph_instance(
        graph_id=graph_id,
        name="Root graph",
        created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        seed="deterministic-seed",
        edges=(("n1", "n2", {"edge_id": "edge-1"}),),
        metadata={"coherence": 0.81},
        last_modified=datetime(2026, 4, 8, 10, 1, tzinfo=timezone.utc),
    )


def test_graph_store_save_and_load_roundtrip(tmp_path: Path) -> None:
    """Saved graph instances should load back as equivalent models."""

    store = GraphStore(root_dir=tmp_path)
    graph_id = "550e8400-e29b-41d4-a716-446655440000"
    instance = _build_graph_instance(graph_id)

    store.save(instance)
    loaded = store.load(graph_id)

    assert loaded.id == instance.id
    assert loaded.graph_data.number_of_nodes() == 2
    assert loaded.graph_data.number_of_edges() == 1
    assert (tmp_path / ".graphs" / f"{graph_id}.json").exists()


def test_graph_store_delete_removes_graph_and_index_entry(tmp_path: Path) -> None:
    """Deleting a graph should remove file storage and summary index rows."""

    store = GraphStore(root_dir=tmp_path)
    graph_id = "550e8400-e29b-41d4-a716-446655440000"
    store.save(_build_graph_instance(graph_id))

    deleted = store.delete(graph_id)

    assert deleted is True
    assert (tmp_path / ".graphs" / f"{graph_id}.json").exists() is False
    assert store.list_graphs() == []


def test_graph_store_load_raises_for_missing_graph(tmp_path: Path) -> None:
    """Loading a missing graph should raise a file-not-found error."""

    store = GraphStore(root_dir=tmp_path)

    with pytest.raises(FileNotFoundError):
        store.load("550e8400-e29b-41d4-a716-446655440000")
