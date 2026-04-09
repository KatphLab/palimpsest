"""Shared builders for graph-instance test data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import networkx as nx
from pydantic import JsonValue

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.seed_config import SeedConfiguration

__all__ = ["build_graph_instance"]


def build_graph_instance(
    *,
    graph_id: str,
    created_at: datetime | None = None,
    last_modified: datetime | None = None,
    name: str | None = None,
    seed: str = "seed-root",
    nodes: Sequence[str] | None = None,
    edges: Sequence[tuple[str, str, Mapping[str, Any]]] | None = None,
    metadata: dict[str, JsonValue] | None = None,
    state: GraphLifecycleState = GraphLifecycleState.ACTIVE,
) -> GraphInstance:
    """Build a GraphInstance with configurable graph topology and metadata."""

    normalized_created_at = created_at or datetime(
        2026, 4, 8, 10, 0, tzinfo=timezone.utc
    )
    normalized_last_modified = last_modified or normalized_created_at

    graph: nx.DiGraph = nx.DiGraph()
    for node in nodes or ("n1", "n2"):
        graph.add_node(node)

    for source, target, attributes in edges or (("n1", "n2", {"edge_id": "edge_1"}),):
        graph.add_edge(source, target, **attributes)

    return GraphInstance(
        id=graph_id,
        name=name or f"Graph {graph_id[:8]}",
        created_at=normalized_created_at,
        seed_config=SeedConfiguration.generate(seed=seed),
        graph_data=graph,
        metadata=metadata or {},
        last_modified=normalized_last_modified,
        state=state,
    )
