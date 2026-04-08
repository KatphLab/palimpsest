"""Integration tests for parallel graph execution behavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

import networkx as nx
import pytest

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from runtime.multi_graph_executor import MultiGraphExecutor


def _build_graph_instance(
    *,
    graph_id: str,
    name: str,
    created_at: datetime,
) -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_node("n3")
    graph.add_edge("n1", "n2", edge_id="edge_1")
    graph.add_edge("n2", "n3", edge_id="edge_2")

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


def test_parallel_execution_maintains_isolation(tmp_path: Path) -> None:
    """Advancing one graph should not mutate execution state of another graph."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 13, 0, tzinfo=timezone.utc)
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

    executor = MultiGraphExecutor(graph_store=store, max_parallel=5)
    asyncio.run(executor.execute_graph(graph_a.id))
    asyncio.run(executor.execute_graph(graph_b.id))

    asyncio.run(executor.advance_step(graph_a.id))
    asyncio.run(executor.advance_step(graph_a.id))

    state_a = asyncio.run(executor.get_execution_state(graph_a.id))
    state_b = asyncio.run(executor.get_execution_state(graph_b.id))

    assert state_a is not None
    assert state_b is not None
    assert state_a.completed_nodes == 2
    assert state_b.completed_nodes == 0

    persisted_a = store.load(graph_a.id)
    persisted_b = store.load(graph_b.id)
    assert persisted_a.last_modified != graph_a.last_modified
    assert persisted_b.last_modified == graph_b.last_modified


def test_rapid_graph_switching_maintains_independent_state(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Rapid alternation should keep states independent and notify conflicts."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 14, 0, tzinfo=timezone.utc)
    graph_a = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440010",
        name="Alpha",
        created_at=created_at,
    )
    graph_b = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440011",
        name="Beta",
        created_at=created_at + timedelta(minutes=1),
    )
    store.save(graph_a)
    store.save(graph_b)

    executor = MultiGraphExecutor(graph_store=store, max_parallel=5)
    asyncio.run(executor.execute_graph(graph_a.id))
    asyncio.run(executor.execute_graph(graph_b.id))

    for _ in range(2):
        asyncio.run(executor.advance_step(graph_a.id))
        asyncio.run(executor.advance_step(graph_b.id))

    stale_remote = store.load(graph_a.id)
    stale_remote.metadata["backgroundUpdate"] = "stale"
    stale_remote.last_modified = stale_remote.last_modified + timedelta(seconds=2)
    store.save(stale_remote)

    with caplog.at_level("WARNING"):
        asyncio.run(executor.advance_step(graph_a.id))

    state_a = asyncio.run(executor.get_execution_state(graph_a.id))
    state_b = asyncio.run(executor.get_execution_state(graph_b.id))
    assert state_a is not None
    assert state_b is not None
    assert state_a.completed_nodes == 3
    assert state_b.completed_nodes == 2

    resolved_graph = store.load(graph_a.id)
    assert "backgroundUpdate" not in resolved_graph.metadata
    assert any("conflict" in record.message.casefold() for record in caplog.records)


def test_background_operations_do_not_block_foreground(tmp_path: Path) -> None:
    """Background steps on one graph should not block foreground operations."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc)
    foreground_graph = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440020",
        name="Foreground",
        created_at=created_at,
    )
    background_graph = _build_graph_instance(
        graph_id="550e8400-e29b-41d4-a716-446655440021",
        name="Background",
        created_at=created_at + timedelta(minutes=1),
    )
    store.save(foreground_graph)
    store.save(background_graph)

    executor = MultiGraphExecutor(graph_store=store, max_parallel=2)
    asyncio.run(executor.execute_graph(foreground_graph.id))
    asyncio.run(executor.execute_graph(background_graph.id))

    async def _scenario() -> float:
        async def _background_loop() -> None:
            for _ in range(2):
                await executor.advance_step(background_graph.id)
                await asyncio.sleep(0.05)

        background_task = asyncio.create_task(_background_loop())
        await asyncio.sleep(0)
        started = perf_counter()
        await executor.advance_step(foreground_graph.id)
        elapsed_ms = (perf_counter() - started) * 1000
        await background_task
        return elapsed_ms

    elapsed_ms = asyncio.run(_scenario())
    usage = asyncio.run(executor.get_resource_usage())

    assert elapsed_ms < 100
    assert usage.active_graphs == 2
    assert usage.warning is not None
