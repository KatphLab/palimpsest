"""Phase 7 performance verification tests for graph operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

from models.graph_instance import GraphInstance
from models.requests import GraphForkRequest, GraphSwitchRequest
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker
from services.graph_manager import GraphManager
from services.graph_switcher import GraphSwitcher
from tests.fixtures import build_graph_instance


def _build_chain_graph_instance(
    *,
    graph_id: str,
    name: str,
    created_at: datetime,
    node_count: int,
    edge_id_prefix: str,
) -> GraphInstance:
    return build_graph_instance(
        graph_id=graph_id,
        name=name,
        created_at=created_at,
        seed=f"seed-{name}",
        nodes=tuple(f"n{index}" for index in range(node_count)),
        edges=tuple(
            (
                f"n{index}",
                f"n{index + 1}",
                {
                    "edge_id": f"{edge_id_prefix}_{index}",
                    "coherence_score": 0.9,
                },
            )
            for index in range(node_count - 1)
        ),
    )


def _percentile(samples_ms: list[float], percentile: float) -> float:
    """Return percentile value from latency samples in milliseconds."""

    if not samples_ms:
        raise ValueError("samples_ms must not be empty")

    if percentile < 0 or percentile > 100:
        raise ValueError("percentile must be between 0 and 100")

    ordered = sorted(samples_ms)
    index = (len(ordered) - 1) * (percentile / 100)
    lower_index = int(index)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = index - lower_index

    return ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight


def test_fork_creation_completes_under_500ms(tmp_path: Path) -> None:
    """Fork creation should satisfy the <500ms CA-005 budget."""

    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)
    source_graph_id = "550e8400-e29b-41d4-a716-446655440000"
    store.save(
        _build_chain_graph_instance(
            graph_id=source_graph_id,
            name="Source",
            created_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
            node_count=1000,
            edge_id_prefix="edge",
        )
    )

    forker = GraphForker(graph_store=store, lineage_store=lineage_store)

    started = perf_counter()
    _ = forker.fork_graph(
        GraphForkRequest(source_graph_id=source_graph_id, fork_edge_id="edge_900")
    )
    elapsed_ms = (perf_counter() - started) * 1000

    assert elapsed_ms < 500


def test_graph_switch_completes_under_300ms_for_1000_nodes(tmp_path: Path) -> None:
    """Graph switching should satisfy the <300ms budget at 1000 nodes."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    target_graph_id = "550e8400-e29b-41d4-a716-446655440001"
    store.save(
        _build_chain_graph_instance(
            graph_id="550e8400-e29b-41d4-a716-446655440000",
            name="Baseline",
            created_at=created_at,
            node_count=8,
            edge_id_prefix="small",
        )
    )
    store.save(
        _build_chain_graph_instance(
            graph_id=target_graph_id,
            name="Large",
            created_at=created_at + timedelta(minutes=1),
            node_count=1000,
            edge_id_prefix="large",
        )
    )

    switcher = GraphSwitcher(graph_store=store)
    _ = switcher.switch_graph(
        GraphSwitchRequest(
            target_graph_id="550e8400-e29b-41d4-a716-446655440000",
        )
    )

    started = perf_counter()
    response = switcher.switch_graph(
        GraphSwitchRequest(target_graph_id=target_graph_id)
    )
    elapsed_ms = (perf_counter() - started) * 1000

    assert response.load_time_ms < 300
    assert elapsed_ms < 300


def test_multi_graph_view_completes_under_200ms_for_50_graphs(tmp_path: Path) -> None:
    """Multi-graph view should satisfy the <200ms budget for 50 graphs."""

    store = GraphStore(root_dir=tmp_path)
    manager = GraphManager(
        graph_store=store, lineage_store=LineageStore(root_dir=tmp_path)
    )
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)

    for index in range(50):
        graph_id = f"550e8400-e29b-41d4-a716-{index:012d}"
        store.save(
            _build_chain_graph_instance(
                graph_id=graph_id,
                name=f"Graph {index:02d}",
                created_at=created_at + timedelta(seconds=index),
                node_count=4,
                edge_id_prefix=f"edge_{index}",
            )
        )

    started = perf_counter()
    view = manager.get_multi_graph_view()
    elapsed_ms = (perf_counter() - started) * 1000

    assert len(view.graphs) == 50
    assert elapsed_ms < 200


def test_graph_switch_feedback_p95_under_300ms_for_ten_graphs(tmp_path: Path) -> None:
    """Switch feedback should stay under 300ms (p95) with 10 graphs loaded."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    graph_ids = [f"550e8400-e29b-41d4-a716-{index:012d}" for index in range(10)]

    for index, graph_id in enumerate(graph_ids):
        store.save(
            _build_chain_graph_instance(
                graph_id=graph_id,
                name=f"Graph {index:02d}",
                created_at=created_at + timedelta(seconds=index),
                node_count=1000,
                edge_id_prefix=f"switch_{index}",
            )
        )

    switcher = GraphSwitcher(graph_store=store)
    _ = switcher.switch_graph(GraphSwitchRequest(target_graph_id=graph_ids[0]))

    load_time_ms_samples: list[float] = []
    elapsed_ms_samples: list[float] = []

    for _ in range(3):
        for graph_id in graph_ids[1:] + graph_ids[:1]:
            started = perf_counter()
            response = switcher.switch_graph(
                GraphSwitchRequest(target_graph_id=graph_id)
            )
            elapsed_ms_samples.append((perf_counter() - started) * 1000)
            load_time_ms_samples.append(response.load_time_ms)

    assert _percentile(load_time_ms_samples, 95) < 300
    assert _percentile(elapsed_ms_samples, 95) < 300


def test_fork_and_multi_graph_view_latency_regression_thresholds(
    tmp_path: Path,
) -> None:
    """Regression guard: fork/view latency stays within CA-005 thresholds."""

    store = GraphStore(root_dir=tmp_path)
    lineage_store = LineageStore(root_dir=tmp_path)

    source_graph_id = "550e8400-e29b-41d4-a716-446655441111"
    store.save(
        _build_chain_graph_instance(
            graph_id=source_graph_id,
            name="Fork Source",
            created_at=datetime(2026, 4, 8, 11, 0, tzinfo=timezone.utc),
            node_count=1000,
            edge_id_prefix="fork_latency",
        )
    )

    forker = GraphForker(graph_store=store, lineage_store=lineage_store)
    fork_samples_ms: list[float] = []
    for _ in range(5):
        started = perf_counter()
        _ = forker.fork_graph(
            GraphForkRequest(
                source_graph_id=source_graph_id,
                fork_edge_id="fork_latency_900",
            )
        )
        fork_samples_ms.append((perf_counter() - started) * 1000)

    manager = GraphManager(graph_store=store, lineage_store=lineage_store)
    view_samples_ms: list[float] = []
    for _ in range(12):
        started = perf_counter()
        _ = manager.get_multi_graph_view()
        view_samples_ms.append((perf_counter() - started) * 1000)

    # p95 protects against meaningful regressions while tolerating occasional noise.
    assert _percentile(fork_samples_ms, 95) < 500
    assert _percentile(view_samples_ms, 95) < 200
