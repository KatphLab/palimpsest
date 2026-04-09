"""Integration tests for graph forking isolation guarantees."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from models.graph_instance import GraphInstance
from models.requests import GraphForkRequest
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker
from tests.fixtures import build_graph_instance


def _build_source_graph(graph_id: str) -> GraphInstance:
    return build_graph_instance(
        graph_id=graph_id,
        name="Root graph",
        created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        seed="root-seed",
        nodes=("n1", "n2", "n3"),
        edges=(
            (
                "n1",
                "n2",
                {
                    "edge_id": "edge_1",
                    "history_label": "locked",
                    "coherence_score": 0.9,
                },
            ),
            (
                "n2",
                "n3",
                {
                    "edge_id": "edge_2",
                    "history_label": "future",
                    "coherence_score": 0.9,
                },
            ),
        ),
        metadata={"state": "root"},
        last_modified=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
    )


def _graph_boundary_signature(
    graph: GraphInstance,
) -> tuple[
    tuple[str, ...],
    tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...],
    tuple[tuple[str, str], ...],
    str,
]:
    """Build a deterministic snapshot of graph state at a fork boundary."""

    nodes = tuple(sorted(str(node_id) for node_id in graph.graph_data.nodes))
    edges = tuple(
        sorted(
            (
                str(source_node_id),
                str(target_node_id),
                tuple(
                    sorted(
                        (str(attribute_key), repr(attribute_value))
                        for attribute_key, attribute_value in edge_data.items()
                    )
                ),
            )
            for source_node_id, target_node_id, edge_data in graph.graph_data.edges(
                data=True
            )
        )
    )
    metadata = tuple(
        sorted(
            (str(metadata_key), repr(metadata_value))
            for metadata_key, metadata_value in graph.metadata.items()
        )
    )
    return nodes, edges, metadata, graph.last_modified.isoformat()


def test_fork_isolation_keeps_parent_and_child_independent(tmp_path: Path) -> None:
    """Mutating a forked graph should not mutate its parent graph state."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(_build_source_graph(source_graph_id))

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    response = forker.fork_graph(
        GraphForkRequest(
            source_graph_id=source_graph_id,
            fork_edge_id="edge_1",
            custom_seed="fork-seed",
        )
    )

    fork_graph = graph_store.load(response.forked_graph_id)

    fork_graph.graph_data.add_node("n_fork")
    fork_graph.graph_data.add_edge("n2", "n_fork", edge_id="edge_fork")
    graph_store.save(fork_graph)

    reloaded_parent_graph = graph_store.load(source_graph_id)
    reloaded_fork_graph = graph_store.load(response.forked_graph_id)

    assert "n_fork" not in reloaded_parent_graph.graph_data.nodes
    assert "n_fork" in reloaded_fork_graph.graph_data.nodes


def test_fork_boundary_preserves_source_graph_snapshot(tmp_path: Path) -> None:
    """Creating a fork should not mutate source graph state at boundary."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    source_graph = _build_source_graph(source_graph_id)
    graph_store.save(source_graph)
    baseline_signature = _graph_boundary_signature(source_graph)

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    response = forker.fork_graph(
        GraphForkRequest(
            source_graph_id=source_graph_id,
            fork_edge_id="edge_1",
            custom_seed="fork-boundary-seed",
        )
    )

    reloaded_parent_graph = graph_store.load(source_graph_id)
    reloaded_fork_graph = graph_store.load(response.forked_graph_id)

    assert _graph_boundary_signature(reloaded_parent_graph) == baseline_signature
    assert reloaded_fork_graph.id != reloaded_parent_graph.id


def test_fork_immutability_keeps_history_snapshot_frozen(tmp_path: Path) -> None:
    """Fork snapshots should freeze history up to the selected fork edge."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(_build_source_graph(source_graph_id))

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    response = forker.fork_graph(
        GraphForkRequest(
            source_graph_id=source_graph_id,
            fork_edge_id="edge_1",
        )
    )

    source_graph = graph_store.load(source_graph_id)
    source_graph.graph_data["n1"]["n2"]["history_label"] = "mutated-parent-history"
    graph_store.save(source_graph)

    fork_graph = graph_store.load(response.forked_graph_id)

    assert fork_graph.graph_data.has_edge("n1", "n2")
    assert fork_graph.graph_data["n1"]["n2"]["history_label"] == "locked"
    assert fork_graph.graph_data.has_edge("n2", "n3") is False
