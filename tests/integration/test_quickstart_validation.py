"""Validation tests for quickstart-documented graph workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore


def _build_graph(*, graph_id: str, edge_id: str = "edge_1") -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_edge("n1", "n2", edge_id=edge_id, coherence_score=0.9)

    now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
    return GraphInstance(
        id=graph_id,
        name=f"Graph {graph_id[:8]}",
        created_at=now,
        seed_config=SeedConfiguration.generate(seed="seed-root"),
        graph_data=graph,
        metadata={},
        last_modified=now,
        state=GraphLifecycleState.ACTIVE,
    )


def test_quickstart_cli_examples_run_as_documented(tmp_path: Path) -> None:
    """Quickstart CLI commands should execute successfully end-to-end."""

    from cli.main import main as cli_main

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    second_graph_id = "550e8400-e29b-41d4-a716-446655440001"
    store = GraphStore(root_dir=tmp_path)
    store.save(_build_graph(graph_id=source_graph_id))
    store.save(_build_graph(graph_id=second_graph_id))

    fork_exit = cli_main(
        [
            "fork",
            "--source",
            source_graph_id,
            "--edge",
            "edge_1",
            "--seed",
            "quickstart-seed",
            "--label",
            "Quickstart Fork",
        ],
        root_dir=tmp_path,
    )
    list_exit = cli_main(["list-graphs", "--status", "active"], root_dir=tmp_path)
    switch_exit = cli_main(
        ["switch-graph", "--target", second_graph_id], root_dir=tmp_path
    )

    assert fork_exit == 0
    assert list_exit == 0
    assert switch_exit == 0


def test_quickstart_python_api_example_runs_successfully(tmp_path: Path) -> None:
    """Quickstart Python API example should run and produce a fork."""

    from models.requests import GraphForkRequest
    from persistence.lineage_store import LineageStore
    from services.graph_forker import GraphForker

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    graph_store.save(_build_graph(graph_id=source_graph_id))

    forker = GraphForker(
        graph_store=graph_store,
        lineage_store=LineageStore(root_dir=tmp_path),
    )
    response = forker.fork_graph(
        GraphForkRequest(
            source_graph_id=source_graph_id,
            fork_edge_id="edge_1",
            custom_seed="quickstart-python-seed",
            label="Quickstart Python Fork",
        )
    )

    assert response.parent_graph_id == source_graph_id
    assert response.seed == "quickstart-python-seed"
