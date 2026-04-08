"""Phase 7 unit tests for graph forking hardening behavior."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import networkx as nx
import pytest

from models.errors import ForkErrorCode
from models.graph_instance import GraphInstance, GraphLifecycleState
from models.requests import GraphForkRequest
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker
from services.graph_manager import GraphManager


def _build_graph_instance(
    *,
    graph_id: str,
    edge_id: str = "edge_1",
    coherence_score: float = 0.9,
    include_cycle: bool = False,
) -> GraphInstance:
    graph: nx.DiGraph = nx.DiGraph()  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_node("n3")
    graph.add_edge("n1", "n2", edge_id=edge_id, coherence_score=coherence_score)
    graph.add_edge("n2", "n3", edge_id="edge_2", coherence_score=0.95)
    if include_cycle:
        graph.add_edge("n2", "n1", edge_id="edge_cycle_return", coherence_score=0.95)

    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    return GraphInstance(
        id=graph_id,
        name=f"Graph {graph_id[:8]}",
        created_at=created_at,
        seed_config=SeedConfiguration.generate(seed="seed-root"),
        graph_data=graph,
        metadata={"state": "root"},
        last_modified=created_at,
        state=GraphLifecycleState.ACTIVE,
    )


def test_fork_of_fork_creates_depth_two_lineage(tmp_path: Path) -> None:
    """Forking a child graph should create a second lineage level."""

    root_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(_build_graph_instance(graph_id=root_graph_id))

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    first = asyncio.run(
        forker.fork_graph(
            GraphForkRequest(source_graph_id=root_graph_id, fork_edge_id="edge_1")
        )
    )
    second = asyncio.run(
        forker.fork_graph(
            GraphForkRequest(
                source_graph_id=first.forked_graph_id, fork_edge_id="edge_1"
            )
        )
    )

    ancestry = lineage_store.get_ancestry(second.forked_graph_id)

    assert [item.depth for item in ancestry] == [1, 2]
    assert ancestry[-1].branch_id.endswith("-d2")


def test_fork_request_rejects_cycle_forming_edge(tmp_path: Path) -> None:
    """Fork validation should reject edges that participate in cycles."""

    root_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    graph_store.save(
        _build_graph_instance(
            graph_id=root_graph_id,
            edge_id="edge_cycle",
            include_cycle=True,
        )
    )

    forker = GraphForker(
        graph_store=graph_store, lineage_store=LineageStore(root_dir=tmp_path)
    )
    is_valid, error = forker.validate_fork_request(
        GraphForkRequest(source_graph_id=root_graph_id, fork_edge_id="edge_cycle")
    )

    assert is_valid is False
    assert error is not None
    assert error.error == ForkErrorCode.FORK_CYCLE_DETECTED


def test_fork_request_rejects_low_coherence_transition(tmp_path: Path) -> None:
    """Fork validation should enforce coherence threshold on transitions."""

    root_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    graph_store.save(
        _build_graph_instance(
            graph_id=root_graph_id,
            edge_id="edge_low_coherence",
            coherence_score=0.4,
        )
    )

    forker = GraphForker(
        graph_store=graph_store, lineage_store=LineageStore(root_dir=tmp_path)
    )
    is_valid, error = forker.validate_fork_request(
        GraphForkRequest(
            source_graph_id=root_graph_id,
            fork_edge_id="edge_low_coherence",
        )
    )

    assert is_valid is False
    assert error is not None
    assert error.error == ForkErrorCode.COHERENCE_VIOLATION


def test_graph_limit_enforcement_returns_graph_limit_error(tmp_path: Path) -> None:
    """Fork validation should fail once the 50-graph limit is reached."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(_build_graph_instance(graph_id=source_graph_id))

    base_created_at = datetime(2026, 4, 8, 11, 0, tzinfo=timezone.utc)
    for index in range(1, 50):
        graph_id = f"550e8400-e29b-41d4-a716-{index:012d}"
        graph = _build_graph_instance(graph_id=graph_id)
        graph.created_at = base_created_at + timedelta(seconds=index)
        graph.last_modified = graph.created_at
        graph_store.save(graph)

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    is_valid, error = forker.validate_fork_request(
        GraphForkRequest(source_graph_id=source_graph_id, fork_edge_id="edge_1")
    )

    assert is_valid is False
    assert error is not None
    assert error.error == ForkErrorCode.GRAPH_LIMIT_EXCEEDED


def test_fork_create_switch_delete_operations_emit_structured_logs(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fork/create/switch/delete flows should emit structured operation logs."""

    root_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    sibling_graph_id = "550e8400-e29b-41d4-a716-446655440001"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(_build_graph_instance(graph_id=root_graph_id))
    graph_store.save(_build_graph_instance(graph_id=sibling_graph_id))

    logger = logging.getLogger("tests.phase7.operations")
    caplog.set_level(logging.INFO, logger="tests.phase7.operations")

    forker = GraphForker(
        graph_store=graph_store,
        lineage_store=lineage_store,
        logger=logger,
    )
    response = asyncio.run(
        forker.fork_graph(
            GraphForkRequest(source_graph_id=root_graph_id, fork_edge_id="edge_1")
        )
    )

    from models.requests import GraphSwitchRequest
    from services.graph_switcher import GraphSwitcher

    switcher = GraphSwitcher(graph_store=graph_store, logger=logger)
    switcher.switch_graph(GraphSwitchRequest(target_graph_id=sibling_graph_id))

    manager = GraphManager(
        graph_store=graph_store, lineage_store=lineage_store, logger=logger
    )
    manager.delete_graph(response.forked_graph_id, force=False)

    payloads = [json.loads(record.message) for record in caplog.records]
    operations = {(payload["operation"], payload["status"]) for payload in payloads}

    assert ("fork", "success") in operations
    assert ("create", "success") in operations
    assert ("switch", "success") in operations
    assert ("delete", "success") in operations
