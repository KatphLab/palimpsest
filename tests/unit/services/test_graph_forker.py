"""Unit tests for GraphForker behavior."""

from __future__ import annotations

import hashlib
import json
import logging
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from models.errors import ForkErrorCode
from models.graph_instance import GraphInstance, GraphLifecycleState
from models.requests import GraphForkRequest, GraphSwitchRequest
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker
from services.graph_manager import GraphManager
from services.graph_switcher import GraphSwitcher
from tests.fixtures import build_graph_instance


def _build_source_graph(*, graph_id: str, edge_id: str = "edge_1") -> GraphInstance:
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    return build_graph_instance(
        graph_id=graph_id,
        name="Root graph",
        created_at=created_at,
        seed="root-seed",
        edges=(("n1", "n2", {"edge_id": edge_id, "coherence_score": 0.9}),),
        metadata={"state": "root"},
        last_modified=created_at,
        state=GraphLifecycleState.CREATED,
    )


def _numeric_state(seed_text: str) -> int:
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _scoped_numeric_state(seed_text: str, scope: str) -> int:
    digest = hashlib.sha256(f"{seed_text}:{scope}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def test_custom_seed_produces_deterministic_output(tmp_path: Path) -> None:
    """Forks with same custom seed should share deterministic seed state."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    store.save(_build_source_graph(graph_id=source_graph_id))

    forker = GraphForker(graph_store=store, lineage_store=lineage_store)
    request = GraphForkRequest(
        source_graph_id=source_graph_id,
        fork_edge_id="edge_1",
        custom_seed="deterministic-seed-42",
    )

    first = forker.fork_graph(request)
    second = forker.fork_graph(request)

    first_graph = store.load(first.forked_graph_id)
    second_graph = store.load(second.forked_graph_id)
    expected_scope = f"{source_graph_id}:edge_1"

    assert first.seed == "deterministic-seed-42"
    assert second.seed == "deterministic-seed-42"
    assert first_graph.metadata["seed_numeric_state"] == _numeric_state(
        "deterministic-seed-42"
    )
    assert second_graph.metadata["seed_numeric_state"] == _numeric_state(
        "deterministic-seed-42"
    )
    assert first_graph.metadata["seed_scope"] == expected_scope
    assert second_graph.metadata["seed_scope"] == expected_scope
    assert first_graph.metadata["seed_scoped_numeric_state"] == _scoped_numeric_state(
        "deterministic-seed-42", expected_scope
    )
    assert second_graph.metadata["seed_scoped_numeric_state"] == _scoped_numeric_state(
        "deterministic-seed-42", expected_scope
    )


def test_auto_generated_seed_when_custom_seed_absent(tmp_path: Path) -> None:
    """Forks without custom seed should auto-generate unique alphanumeric seeds."""

    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    store.save(_build_source_graph(graph_id=source_graph_id))

    forker = GraphForker(graph_store=store, lineage_store=lineage_store)

    first = forker.fork_graph(
        GraphForkRequest(source_graph_id=source_graph_id, fork_edge_id="edge_1")
    )
    second = forker.fork_graph(
        GraphForkRequest(source_graph_id=source_graph_id, fork_edge_id="edge_1")
    )

    first_graph = store.load(first.forked_graph_id)

    assert len(first.seed) == 16
    assert all(
        character in string.ascii_letters + string.digits for character in first.seed
    )
    assert len(second.seed) == 16
    assert all(
        character in string.ascii_letters + string.digits for character in second.seed
    )
    assert first.seed != second.seed
    assert first_graph.metadata["seed_numeric_state"] == _numeric_state(first.seed)


def _build_graph_instance(
    *,
    graph_id: str,
    edge_id: str = "edge_1",
    coherence_score: float = 0.9,
    include_cycle: bool = False,
) -> GraphInstance:
    """Build a GraphInstance with configurable properties for testing."""
    edges: list[tuple[str, str, dict[str, object]]] = [
        ("n1", "n2", {"edge_id": edge_id, "coherence_score": coherence_score}),
        ("n2", "n3", {"edge_id": "edge_2", "coherence_score": 0.95}),
    ]
    if include_cycle:
        edges.append(
            (
                "n2",
                "n1",
                {"edge_id": "edge_cycle_return", "coherence_score": 0.95},
            )
        )

    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    return build_graph_instance(
        graph_id=graph_id,
        created_at=created_at,
        nodes=("n1", "n2", "n3"),
        edges=edges,
        metadata={"state": "root"},
        last_modified=created_at,
    )


def test_fork_of_fork_creates_depth_two_lineage(tmp_path: Path) -> None:
    """Forking a child graph should create a second lineage level."""

    root_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    graph_store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    graph_store.save(_build_graph_instance(graph_id=root_graph_id))

    forker = GraphForker(graph_store=graph_store, lineage_store=lineage_store)
    first = forker.fork_graph(
        GraphForkRequest(source_graph_id=root_graph_id, fork_edge_id="edge_1")
    )
    second = forker.fork_graph(
        GraphForkRequest(source_graph_id=first.forked_graph_id, fork_edge_id="edge_1")
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
    response = forker.fork_graph(
        GraphForkRequest(source_graph_id=root_graph_id, fork_edge_id="edge_1")
    )

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
