"""Validation tests for quickstart-documented graph workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.requests import GraphForkRequest
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker


def _build_graph(*, graph_id: str, edge_id: str = "edge_1") -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()
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


def test_quickstart_python_api_example_runs_successfully(tmp_path: Path) -> None:
    """Quickstart Python API example should run and produce a fork."""

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
