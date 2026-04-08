"""Unit tests for GraphForker seed handling behavior."""

from __future__ import annotations

import hashlib
import string
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from models.graph_instance import GraphInstance
from models.requests import GraphForkRequest
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker


def _build_source_graph(*, graph_id: str, edge_id: str = "edge_1") -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_edge("n1", "n2", edge_id=edge_id, coherence_score=0.9)

    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    return GraphInstance(
        id=graph_id,
        name="Root graph",
        created_at=created_at,
        seed_config=SeedConfiguration.generate(seed="root-seed"),
        graph_data=graph,
        metadata={"state": "root"},
        last_modified=created_at,
    )


def _numeric_state(seed_text: str) -> int:
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _scoped_numeric_state(seed_text: str, scope: str) -> int:
    digest = hashlib.sha256(f"{seed_text}:{scope}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def test_custom_seed_produces_deterministic_output(tmp_path: Path) -> None:
    """Forks with same custom seed should share deterministic seed state."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    store.save(_build_source_graph(graph_id=source_graph_id))

    forker = GraphForker(graph_store=store, lineage_store=lineage_store)
    request = GraphForkRequest(
        source_graph_id=source_graph_id,
        fork_edge_id="edge_1",
        custom_seed="deterministic-seed-42",
    )

    first = forker.fork_graph(request)
    second = forker.fork_graph(request)

    first_graph = store.load(first.forked_graph_id)
    second_graph = store.load(second.forked_graph_id)
    expected_scope = f"{source_graph_id}:edge_1"

    assert first.seed == "deterministic-seed-42"
    assert second.seed == "deterministic-seed-42"
    assert first_graph.metadata["seed_numeric_state"] == _numeric_state(
        "deterministic-seed-42"
    )
    assert second_graph.metadata["seed_numeric_state"] == _numeric_state(
        "deterministic-seed-42"
    )
    assert first_graph.metadata["seed_scope"] == expected_scope
    assert second_graph.metadata["seed_scope"] == expected_scope
    assert first_graph.metadata["seed_scoped_numeric_state"] == _scoped_numeric_state(
        "deterministic-seed-42", expected_scope
    )
    assert second_graph.metadata["seed_scoped_numeric_state"] == _scoped_numeric_state(
        "deterministic-seed-42", expected_scope
    )


def test_auto_generated_seed_when_custom_seed_absent(tmp_path: Path) -> None:
    """Forks without custom seed should auto-generate unique alphanumeric seeds."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    store.save(_build_source_graph(graph_id=source_graph_id))

    forker = GraphForker(graph_store=store, lineage_store=lineage_store)

    first = forker.fork_graph(
        GraphForkRequest(source_graph_id=source_graph_id, fork_edge_id="edge_1")
    )
    second = forker.fork_graph(
        GraphForkRequest(source_graph_id=source_graph_id, fork_edge_id="edge_1")
    )

    first_graph = store.load(first.forked_graph_id)

    assert len(first.seed) == 16
    assert all(
        character in string.ascii_letters + string.digits for character in first.seed
    )
    assert len(second.seed) == 16
    assert all(
        character in string.ascii_letters + string.digits for character in second.seed
    )
    assert first.seed != second.seed
    assert first_graph.metadata["seed_numeric_state"] == _numeric_state(first.seed)
