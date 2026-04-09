"""Tests for the GraphInstance model."""

from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx
import pytest
from pydantic import ValidationError

from models.fork_point import ForkPoint
from models.graph_instance import GraphInstance
from models.seed_config import SeedConfiguration


def _sample_graph() -> nx.DiGraph:
    graph: nx.DiGraph = nx.DiGraph()
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_edge("n1", "n2", edge_id="edge-1")
    return graph


def test_graph_instance_accepts_valid_data() -> None:
    """Graph instances should accept valid model dependencies and graph data."""

    graph = _sample_graph()
    instance = GraphInstance(
        id="550e8400-e29b-41d4-a716-446655440000",
        name="Root graph",
        created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        fork_point=ForkPoint(
            source_graph_id="550e8400-e29b-41d4-a716-446655440001",
            fork_edge_id="edge-1",
            timestamp=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
        ),
        seed_config=SeedConfiguration.generate(seed="deterministic-seed"),
        graph_data=graph,
        metadata={"coherence": 0.81},
        last_modified=datetime(2026, 4, 8, 10, 1, tzinfo=timezone.utc),
    )

    assert instance.id == "550e8400-e29b-41d4-a716-446655440000"
    assert instance.graph_data.number_of_nodes() == 2
    assert instance.to_summary().node_count == 2


def test_graph_instance_rejects_non_digraph_data() -> None:
    """Graph instances should require NetworkX DiGraph payloads."""

    with pytest.raises(ValidationError):
        GraphInstance.model_validate(
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Root graph",
                "created_at": datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
                "seed_config": SeedConfiguration.generate(seed="deterministic-seed"),
                "graph_data": {"nodes": []},
                "metadata": {},
                "last_modified": datetime(
                    2026,
                    4,
                    8,
                    10,
                    1,
                    tzinfo=timezone.utc,
                ),
            }
        )


def test_graph_instance_rejects_blank_name() -> None:
    """Graph instances should enforce a non-empty graph name."""

    with pytest.raises(ValidationError):
        GraphInstance(
            id="550e8400-e29b-41d4-a716-446655440000",
            name=" ",
            created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
            seed_config=SeedConfiguration.generate(seed="deterministic-seed"),
            graph_data=_sample_graph(),
            metadata={},
            last_modified=datetime(2026, 4, 8, 10, 1, tzinfo=timezone.utc),
        )
