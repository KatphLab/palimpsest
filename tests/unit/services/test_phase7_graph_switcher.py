"""Phase 7 tests for graph switcher optimistic-locking behavior."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import networkx as nx
import pytest

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.requests import GraphSwitchRequest
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from services.graph_switcher import GraphSwitcher


def _build_graph_instance(*, graph_id: str, created_at: datetime) -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_edge("n1", "n2", edge_id="edge_1", coherence_score=0.9)

    return GraphInstance(
        id=graph_id,
        name=f"Graph {graph_id[:8]}",
        created_at=created_at,
        seed_config=SeedConfiguration.generate(seed="seed-root"),
        graph_data=graph,
        metadata={},
        last_modified=created_at,
        state=GraphLifecycleState.ACTIVE,
    )


def test_switch_graph_logs_optimistic_lock_conflict(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Switching should emit a conflict log when active graph is stale."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    active_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    target_graph_id = "550e8400-e29b-41d4-a716-446655440001"
    store.save(_build_graph_instance(graph_id=active_graph_id, created_at=created_at))
    store.save(
        _build_graph_instance(
            graph_id=target_graph_id,
            created_at=created_at + timedelta(minutes=1),
        )
    )

    logger = logging.getLogger("tests.phase7.switcher")
    caplog.set_level(logging.WARNING, logger="tests.phase7.switcher")
    switcher = GraphSwitcher(graph_store=store, logger=logger)

    asyncio.run(
        switcher.switch_graph(GraphSwitchRequest(target_graph_id=active_graph_id))
    )

    stale_remote = store.load(active_graph_id)
    stale_remote.last_modified = stale_remote.last_modified + timedelta(seconds=5)
    stale_remote.metadata["background"] = "updated"
    store.save(stale_remote)

    asyncio.run(
        switcher.switch_graph(GraphSwitchRequest(target_graph_id=target_graph_id))
    )

    payloads = [json.loads(record.message) for record in caplog.records]
    assert any(
        payload["operation"] == "switch" and payload["status"] == "conflict"
        for payload in payloads
    )
