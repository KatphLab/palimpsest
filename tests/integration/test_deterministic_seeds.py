"""Integration tests for deterministic fork seed behavior."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from models.graph_instance import GraphInstance
from models.requests import GraphForkRequest
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker


def _build_source_graph(
    *, graph_id: str, edge_id: str = "edge_1", metadata_state: str = "root"
) -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_edge("n1", "n2", edge_id=edge_id, narrative="A forking decision.")

    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    return GraphInstance(
        id=graph_id,
        name=f"Graph {graph_id[:8]}",
        created_at=created_at,
        seed_config=SeedConfiguration.generate(seed=f"seed-{graph_id[:8]}"),
        graph_data=graph,
        metadata={"state": metadata_state},
        last_modified=created_at,
    )


def _hash64(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def test_deterministic_reproduction_with_same_seed(tmp_path: Path) -> None:
    """Same source, edge, and seed should produce identical fork content."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(_build_source_graph(graph_id=source_graph_id))

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    request = GraphForkRequest(
        source_graph_id=source_graph_id,
        fork_edge_id="edge_1",
        custom_seed="reproducible-seed-42",
    )

    first = asyncio.run(forker.fork_graph(request))
    second = asyncio.run(forker.fork_graph(request))

    first_graph = graph_store.load(first.forked_graph_id)
    second_graph = graph_store.load(second.forked_graph_id)

    assert first.forked_graph_id != second.forked_graph_id
    assert first.seed == second.seed == "reproducible-seed-42"
    assert set(first_graph.graph_data.nodes()) == set(second_graph.graph_data.nodes())
    assert set(first_graph.graph_data.edges()) == set(second_graph.graph_data.edges())
    assert first_graph.metadata["seed_numeric_state"] == _hash64("reproducible-seed-42")
    assert second_graph.metadata["seed_numeric_state"] == _hash64(
        "reproducible-seed-42"
    )


def test_seed_scoping_same_seed_different_graphs_has_independent_sequences(
    tmp_path: Path,
) -> None:
    """Same seed across different source graphs should not share scoped RNG state."""

    first_source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    second_source_graph_id = "550e8400-e29b-41d4-a716-446655440001"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(
        _build_source_graph(
            graph_id=first_source_graph_id,
            metadata_state="alpha",
        )
    )
    graph_store.save(
        _build_source_graph(
            graph_id=second_source_graph_id,
            metadata_state="beta",
        )
    )

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    seed_value = "shared-seed"
    first = asyncio.run(
        forker.fork_graph(
            GraphForkRequest(
                source_graph_id=first_source_graph_id,
                fork_edge_id="edge_1",
                custom_seed=seed_value,
            )
        )
    )
    second = asyncio.run(
        forker.fork_graph(
            GraphForkRequest(
                source_graph_id=second_source_graph_id,
                fork_edge_id="edge_1",
                custom_seed=seed_value,
            )
        )
    )

    first_graph = graph_store.load(first.forked_graph_id)
    second_graph = graph_store.load(second.forked_graph_id)

    first_scope = f"{first_source_graph_id}:edge_1"
    second_scope = f"{second_source_graph_id}:edge_1"

    assert first_graph.metadata["seed_numeric_state"] == _hash64(seed_value)
    assert second_graph.metadata["seed_numeric_state"] == _hash64(seed_value)
    assert first_graph.metadata["seed_scope"] == first_scope
    assert second_graph.metadata["seed_scope"] == second_scope
    assert first_graph.metadata["seed_scoped_numeric_state"] == _hash64(
        f"{seed_value}:{first_scope}"
    )
    assert second_graph.metadata["seed_scoped_numeric_state"] == _hash64(
        f"{seed_value}:{second_scope}"
    )
    assert (
        first_graph.metadata["seed_scoped_numeric_state"]
        != second_graph.metadata["seed_scoped_numeric_state"]
    )
