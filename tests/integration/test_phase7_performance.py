"""Phase 7 performance verification tests for graph operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

import networkx as nx

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.requests import GraphForkRequest, GraphSwitchRequest
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker
from services.graph_manager import GraphManager
from services.graph_switcher import GraphSwitcher


def _build_chain_graph_instance(
    *,
    graph_id: str,
    name: str,
    created_at: datetime,
    node_count: int,
    edge_id_prefix: str,
) -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    for index in range(node_count):
        graph.add_node(f"n{index}")
    for index in range(node_count - 1):
        graph.add_edge(
            f"n{index}",
            f"n{index + 1}",
            edge_id=f"{edge_id_prefix}_{index}",
            coherence_score=0.9,
        )

    return GraphInstance(
        id=graph_id,
        name=name,
        created_at=created_at,
        seed_config=SeedConfiguration.generate(seed=f"seed-{name}"),
        graph_data=graph,
        metadata={},
        last_modified=created_at,
        state=GraphLifecycleState.ACTIVE,
    )


def test_fork_creation_completes_under_500ms(tmp_path: Path) -> None:
    """Fork creation should satisfy the <500ms CA-005 budget."""

    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    store.save(
        _build_chain_graph_instance(
            graph_id=source_graph_id,
            name="Source",
            created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
            node_count=1000,
            edge_id_prefix="edge",
        )
    )

    forker = GraphForker(graph_store=store, lineage_store=lineage_store)

    started = perf_counter()
    _ = forker.fork_graph(
        GraphForkRequest(source_graph_id=source_graph_id, fork_edge_id="edge_900")
    )
    elapsed_ms = (perf_counter() - started) * 1000

    assert elapsed_ms < 500


def test_graph_switch_completes_under_300ms_for_1000_nodes(tmp_path: Path) -> None:
    """Graph switching should satisfy the <300ms budget at 1000 nodes."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    target_graph_id = "550e8400-e29b-41d4-a716-446655440001"
    store.save(
        _build_chain_graph_instance(
            graph_id="550e8400-e29b-41d4-a716-446655440000",
            name="Baseline",
            created_at=created_at,
            node_count=8,
            edge_id_prefix="small",
        )
    )
    store.save(
        _build_chain_graph_instance(
            graph_id=target_graph_id,
            name="Large",
            created_at=created_at + timedelta(minutes=1),
            node_count=1000,
            edge_id_prefix="large",
        )
    )

    switcher = GraphSwitcher(graph_store=store)
    _ = switcher.switch_graph(
        GraphSwitchRequest(
            target_graph_id="550e8400-e29b-41d4-a716-446655440000",
        )
    )

    started = perf_counter()
    response = switcher.switch_graph(
        GraphSwitchRequest(target_graph_id=target_graph_id)
    )
    elapsed_ms = (perf_counter() - started) * 1000

    assert response.load_time_ms < 300
    assert elapsed_ms < 300


def test_multi_graph_view_completes_under_200ms_for_50_graphs(tmp_path: Path) -> None:
    """Multi-graph view should satisfy the <200ms budget for 50 graphs."""

    store = GraphStore(root_dir=tmp_path)
    manager = GraphManager(
        graph_store=store, lineage_store=LineageStore(root_dir=tmp_path)
    )
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)

    for index in range(50):
        graph_id = f"550e8400-e29b-41d4-a716-{index:012d}"
        store.save(
            _build_chain_graph_instance(
                graph_id=graph_id,
                name=f"Graph {index:02d}",
                created_at=created_at + timedelta(seconds=index),
                node_count=4,
                edge_id_prefix=f"edge_{index}",
            )
        )

    started = perf_counter()
    view = manager.get_multi_graph_view()
    elapsed_ms = (perf_counter() - started) * 1000

    assert len(view.graphs) == 50
    assert elapsed_ms < 200
