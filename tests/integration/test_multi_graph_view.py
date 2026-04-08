"""Integration tests for multi-graph browsing and switching flows."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

import networkx as nx

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.requests import GraphSwitchRequest
from models.seed_config import SeedConfiguration
from models.views import FilterState, ViewPreferences
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_manager import GraphManager
from services.graph_switcher import GraphSwitcher


def _build_graph_instance(
    *,
    graph_id: str,
    name: str,
    created_at: datetime,
    state: GraphLifecycleState = GraphLifecycleState.ACTIVE,
) -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_edge("n1", "n2", edge_id="edge_1")

    return GraphInstance(
        id=graph_id,
        name=name,
        created_at=created_at,
        seed_config=SeedConfiguration.generate(seed=f"seed-{name}"),
        graph_data=graph,
        metadata={},
        last_modified=created_at,
        state=state,
    )


def test_multi_graph_view_returns_all_active_graphs(tmp_path: Path) -> None:
    """Multi-graph queries should include all active graphs with filtering/sorting."""

    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    active_a = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        name="Alpha",
        created_at=created_at,
    )
    active_b = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        name="Beta",
        created_at=created_at + timedelta(minutes=1),
    )
    archived = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440002",
        name="Gamma",
        created_at=created_at + timedelta(minutes=2),
        state=GraphLifecycleState.ARCHIVED,
    )
    store.save(active_a)
    store.save(active_b)
    store.save(archived)

    manager = GraphManager(graph_store=store, lineage_store=lineage_store)

    view = asyncio.run(
        manager.get_multi_graph_view(
            filters=FilterState(status="active"),
            view_prefs=ViewPreferences(sort_by="name", sort_order="asc"),
            active_graph_id=active_a.id,
        )
    )

    assert [summary.name for summary in view.graphs] == ["Alpha", "Beta"]
    assert view.active_graph_id == active_a.id
    assert view.total_count == 3


def test_graph_switch_loads_correct_state(tmp_path: Path) -> None:
    """Switching graphs should return the selected graph summary and timing."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    graph_a = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        name="Alpha",
        created_at=created_at,
    )
    graph_b = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440001",
        name="Beta",
        created_at=created_at + timedelta(minutes=1),
    )
    store.save(graph_a)
    store.save(graph_b)

    switcher = GraphSwitcher(graph_store=store)
    first = asyncio.run(
        switcher.switch_graph(GraphSwitchRequest(target_graph_id=graph_a.id))
    )
    second = asyncio.run(
        switcher.switch_graph(GraphSwitchRequest(target_graph_id=graph_b.id))
    )

    assert first.previous_graph_id is None
    assert second.previous_graph_id == graph_a.id
    assert second.current_graph_id == graph_b.id
    assert second.graph_summary.name == "Beta"
    assert second.load_time_ms >= 0


def test_multi_graph_view_performance_under_200ms_for_50_graphs(tmp_path: Path) -> None:
    """Graph manager should return 50-graph summaries within the CA-005 budget."""

    store = GraphStore(root_dir=tmp_path)
    manager = GraphManager(
        graph_store=store, lineage_store=LineageStore(root_dir=tmp_path)
    )
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)

    for index in range(50):
        graph_id = f"550e8400-e29b-41d4-a716-{index:012d}"
        store.save(
            _build_graph_instance(
                graph_id=graph_id,
                name=f"Graph {index:02d}",
                created_at=created_at + timedelta(seconds=index),
            )
        )

    started = perf_counter()
    view = asyncio.run(manager.get_multi_graph_view())
    elapsed_ms = (perf_counter() - started) * 1000

    assert len(view.graphs) == 50
    assert elapsed_ms < 200
