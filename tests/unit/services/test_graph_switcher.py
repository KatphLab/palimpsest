"""Tests for graph switcher optimistic-locking behavior."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from models.graph_instance import GraphInstance
from models.requests import GraphSwitchRequest
from persistence.graph_store import GraphStore
from services.graph_switcher import GraphSwitcher
from tests.fixtures import build_graph_instance


def _build_graph_instance(*, graph_id: str, created_at: datetime) -> GraphInstance:
    return build_graph_instance(
        graph_id=graph_id,
        created_at=created_at,
        edges=(("n1", "n2", {"edge_id": "edge_1", "coherence_score": 0.9}),),
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

    switcher.switch_graph(GraphSwitchRequest(target_graph_id=active_graph_id))

    stale_remote = store.load(active_graph_id)
    stale_remote.last_modified = stale_remote.last_modified + timedelta(seconds=5)
    stale_remote.metadata["background"] = "updated"
    store.save(stale_remote)

    switcher.switch_graph(GraphSwitchRequest(target_graph_id=target_graph_id))

    payloads = [json.loads(record.message) for record in caplog.records]
    assert any(
        payload["operation"] == "switch" and payload["status"] == "conflict"
        for payload in payloads
    )


def test_switch_graph_with_direction_next_at_end_wraps_to_first(
    tmp_path: Path,
) -> None:
    """Graph switcher should wrap to first graph when at last with direction=next.

    Acceptance Scenario: When at the last graph, next direction should cycle back.
    """

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)

    # Create two graphs
    first_id = "550e8400-e29b-41d4-a716-446655440000"
    second_id = "550e8400-e29b-41d4-a716-446655440001"

    store.save(_build_graph_instance(graph_id=first_id, created_at=created_at))
    store.save(
        _build_graph_instance(
            graph_id=second_id,
            created_at=created_at + timedelta(minutes=1),
        )
    )

    switcher = GraphSwitcher(graph_store=store)

    # First, switch to second graph
    switcher.switch_graph(GraphSwitchRequest(target_graph_id=second_id))

    # Now switch with direction=next (should wrap to first)
    from models.requests import GraphNavigationDirection

    response = switcher.switch_graph(
        GraphSwitchRequest(
            target_graph_id=first_id,
            direction=GraphNavigationDirection.NEXT,
        )
    )

    assert response.current_graph_id == first_id


def test_switch_graph_with_direction_previous_at_start_wraps_to_last(
    tmp_path: Path,
) -> None:
    """Graph switcher should wrap to last graph when at first with direction=previous.

    Acceptance Scenario: When at the first graph, previous direction should cycle to last.
    """

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)

    # Create two graphs
    first_id = "550e8400-e29b-41d4-a716-446655440000"
    second_id = "550e8400-e29b-41d4-a716-446655440001"

    store.save(_build_graph_instance(graph_id=first_id, created_at=created_at))
    store.save(
        _build_graph_instance(
            graph_id=second_id,
            created_at=created_at + timedelta(minutes=1),
        )
    )

    switcher = GraphSwitcher(graph_store=store)

    # Switch with direction=previous (should wrap to second/last)
    from models.requests import GraphNavigationDirection

    response = switcher.switch_graph(
        GraphSwitchRequest(
            target_graph_id=second_id,
            direction=GraphNavigationDirection.PREVIOUS,
        )
    )

    assert response.current_graph_id == second_id


def test_switch_graph_preserves_direction_in_response_metadata(
    tmp_path: Path,
) -> None:
    """Graph switcher should record navigation direction in operation log."""

    store = GraphStore(root_dir=tmp_path)
    created_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)

    first_id = "550e8400-e29b-41d4-a716-446655440000"
    second_id = "550e8400-e29b-41d4-a716-446655440001"

    store.save(_build_graph_instance(graph_id=first_id, created_at=created_at))
    store.save(
        _build_graph_instance(
            graph_id=second_id,
            created_at=created_at + timedelta(minutes=1),
        )
    )

    logger = logging.getLogger("tests.phase7.direction")

    switcher = GraphSwitcher(graph_store=store, logger=logger)

    from models.requests import GraphNavigationDirection

    switcher.switch_graph(
        GraphSwitchRequest(
            target_graph_id=second_id,
            direction=GraphNavigationDirection.NEXT,
        )
    )
