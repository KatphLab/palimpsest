"""Integration tests for parallel graph execution behavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models.execution import ExecutionStatus
from models.graph_instance import GraphInstance
from models.graph_session import GraphSession
from persistence.graph_store import GraphStore
from runtime.multi_graph_executor import MultiGraphExecutor
from tests.fixtures import build_graph_instance


def _build_graph_instance(
    *,
    graph_id: str,
    name: str,
    created_at: datetime,
) -> GraphInstance:
    return build_graph_instance(
        graph_id=graph_id,
        name=name,
        created_at=created_at,
        seed=f"seed-{name}",
        nodes=("n1", "n2", "n3"),
        edges=(
            ("n1", "n2", {"edge_id": "edge_1"}),
            ("n2", "n3", {"edge_id": "edge_2"}),
        ),
    )


def test_parallel_execution_maintains_isolation(tmp_path: Path) -> None:
    """Starting one graph should not mutate execution state of another graph."""

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

    executor = MultiGraphExecutor(max_parallel=5)
    executor.register_graph(GraphSession(graph_id=graph_a.id, current_node_id="n1"))
    executor.register_graph(GraphSession(graph_id=graph_b.id, current_node_id="n1"))
    executor.start_graph(graph_a.id)

    state_a = executor.get_execution_state(graph_a.id)
    state_b = executor.get_execution_state(graph_b.id)

    assert state_a is not None
    assert state_b is not None
    assert state_a.status == ExecutionStatus.RUNNING
    assert state_b.status == ExecutionStatus.IDLE

    persisted_a = store.load(graph_a.id)
    persisted_b = store.load(graph_b.id)
    assert persisted_a.last_modified == graph_a.last_modified
    assert persisted_b.last_modified == graph_b.last_modified


def test_rapid_graph_switching_maintains_independent_state(tmp_path: Path) -> None:
    """Rapid alternation keeps focus and execution states independent."""

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

    executor = MultiGraphExecutor(max_parallel=5)
    executor.register_graph(GraphSession(graph_id=graph_a.id, current_node_id="n1"))
    executor.register_graph(GraphSession(graph_id=graph_b.id, current_node_id="n1"))

    first_active = executor.get_active_session()
    assert first_active is not None
    assert first_active.graph_id == graph_a.id

    executor.start_graph(graph_a.id)
    executor.switch_to_next()
    executor.start_graph(graph_b.id)
    executor.pause_graph(graph_a.id)
    executor.switch_to_previous()

    state_a = executor.get_execution_state(graph_a.id)
    state_b = executor.get_execution_state(graph_b.id)
    active = executor.get_active_session()

    assert state_a is not None
    assert state_b is not None
    assert active is not None
    assert active.graph_id == graph_a.id
    assert state_a.status == ExecutionStatus.PAUSED
    assert state_b.status == ExecutionStatus.RUNNING


def test_background_operations_do_not_block_foreground(tmp_path: Path) -> None:
    """Background updates on one graph should not block another graph."""

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

    executor = MultiGraphExecutor(max_parallel=2)
    executor.register_graph(
        GraphSession(graph_id=foreground_graph.id, current_node_id="n1")
    )
    executor.register_graph(
        GraphSession(graph_id=background_graph.id, current_node_id="n1")
    )

    async def _scenario() -> None:
        async def _background_loop() -> None:
            for _ in range(20):
                await asyncio.to_thread(executor.start_graph, background_graph.id)
                await asyncio.to_thread(executor.pause_graph, background_graph.id)

        await asyncio.wait_for(
            asyncio.gather(
                _background_loop(),
                asyncio.to_thread(executor.start_graph, foreground_graph.id),
            ),
            timeout=1.0,
        )

    asyncio.run(_scenario())
    foreground_state = executor.get_execution_state(foreground_graph.id)
    background_state = executor.get_execution_state(background_graph.id)
    snapshot = executor.get_status_snapshot()

    assert foreground_state is not None
    assert background_state is not None
    assert foreground_state.status == ExecutionStatus.RUNNING
    assert background_state.status == ExecutionStatus.PAUSED
    assert snapshot.total_graphs == 2
