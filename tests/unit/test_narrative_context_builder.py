"""Tests for extracting narrative context from the live session graph."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from graph.session_graph import SessionGraph
from models.common import (
    BudgetTelemetry,
    CheckStatus,
    CoherenceSnapshot,
    NodeKind,
    RelationType,
    SessionStatus,
    TerminationVoteState,
)
from models.graph import GraphEdge, GraphNode
from models.narrative_context import (
    NarrativeContext,
    NarrativeGraphCounters,
    NarrativeSceneContext,
)
from models.session import Session
from utils.narrative_context_builder import NarrativeContextBuilder


def _build_session(
    *, graph_version: int = 0, active_node_ids: list[str] | None = None
) -> Session:
    """Build a deterministic live session for unit tests."""

    now = datetime(2026, 4, 7, 0, 0, tzinfo=timezone.utc)
    return Session(
        session_id=uuid4(),
        status=SessionStatus.RUNNING,
        seed_text="Seed text",
        graph_version=graph_version,
        active_node_ids=active_node_ids or [],
        created_at=now,
        updated_at=now,
        coherence=CoherenceSnapshot(
            global_score=1.0,
            local_scores=[],
            global_check_status=CheckStatus.PASS,
            sampled_at=now,
            checked_by="test",
        ),
        budget=BudgetTelemetry(
            estimated_cost_usd=Decimal("0.00"),
            budget_limit_usd=Decimal("5.00"),
            token_input_count=0,
            token_output_count=0,
            model_call_count=0,
        ),
        termination=TerminationVoteState(
            active_node_count=max(len(active_node_ids or []), 1),
            votes_for_termination=0,
            votes_against_termination=1,
            majority_threshold=0.6,
            last_updated_at=now,
        ),
    )


def _add_node(
    session_graph: SessionGraph,
    *,
    session_id: UUID,
    node_id: str,
    node_kind: NodeKind,
    text: str,
) -> None:
    """Add a typed node to the graph fixture."""

    session_graph.add_node(
        GraphNode(
            node_id=node_id,
            session_id=session_id,
            node_kind=node_kind,
            text=text,
        )
    )


def _add_edge(
    session_graph: SessionGraph,
    *,
    session_id: UUID,
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    relation_type: RelationType,
) -> None:
    """Add a typed edge to the graph fixture."""

    session_graph.add_edge(
        GraphEdge(
            edge_id=edge_id,
            session_id=session_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=relation_type,
        )
    )


def test_build_collects_the_last_two_scenes_in_narrative_order() -> None:
    """The builder should return the last two scenes in path order."""

    session = _build_session(active_node_ids=["seed", "scene-2"])
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A seed sentence",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1",
        node_kind=NodeKind.SCENE,
        text="The lantern flickers on the quay.",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-2",
        node_kind=NodeKind.SCENE,
        text="A bell answers from the fog.",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-3",
        node_kind=NodeKind.SCENE,
        text="The harbor gates open at dawn.",
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="seed->scene-1",
        source_node_id="seed",
        target_node_id="scene-1",
        relation_type=RelationType.FOLLOWS,
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="scene-1->scene-2",
        source_node_id="scene-1",
        target_node_id="scene-2",
        relation_type=RelationType.BRANCHES_FROM,
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="scene-2->scene-3",
        source_node_id="scene-2",
        target_node_id="scene-3",
        relation_type=RelationType.FOLLOWS,
    )

    context = NarrativeContextBuilder().build(
        session=session,
        session_graph=session_graph,
        activation_candidate_id="scene-3",
    )

    assert context == NarrativeContext(
        session_id=session_id,
        seed_node_id="seed",
        previous_scene_node_id="scene-2",
        current_scene_node_id="scene-3",
        last_two_scenes=[
            NarrativeSceneContext(
                scene_node_id="scene-2",
                scene_text="A bell answers from the fog.",
            ),
            NarrativeSceneContext(
                scene_node_id="scene-3",
                scene_text="The harbor gates open at dawn.",
            ),
        ],
        graph_counters=NarrativeGraphCounters(
            graph_version=0,
            node_count=4,
            edge_count=3,
            active_node_count=2,
        ),
    )


def test_build_pads_a_single_scene_context() -> None:
    """The builder should gracefully pad when only one scene exists."""

    from utils.narrative_context_builder import NarrativeContextBuilder

    session = _build_session(active_node_ids=["seed", "scene-1"])
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A seed sentence",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1",
        node_kind=NodeKind.SCENE,
        text="A lone lantern burns in the rain.",
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="seed->scene-1",
        source_node_id="seed",
        target_node_id="scene-1",
        relation_type=RelationType.FOLLOWS,
    )

    context = NarrativeContextBuilder().build(
        session=session,
        session_graph=session_graph,
        activation_candidate_id="scene-1",
    )

    assert context.last_two_scenes == [
        NarrativeSceneContext(
            scene_node_id="scene-1",
            scene_text="A lone lantern burns in the rain.",
        ),
        NarrativeSceneContext(
            scene_node_id="scene-1",
            scene_text="A lone lantern burns in the rain.",
        ),
    ]
    assert context.previous_scene_node_id == "scene-1"
    assert context.current_scene_node_id == "scene-1"


@pytest.mark.parametrize("activation_candidate_id", [None, "", "   "])
def test_build_rejects_missing_or_blank_activation_candidate_ids(
    activation_candidate_id: str | None,
) -> None:
    """The builder should require a usable activation candidate id."""

    session = _build_session(active_node_ids=["seed", "scene-1"])
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A seed sentence",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1",
        node_kind=NodeKind.SCENE,
        text="A lone lantern burns in the rain.",
    )

    with pytest.raises(ValueError):
        NarrativeContextBuilder().build(
            session=session,
            session_graph=session_graph,
            activation_candidate_id=activation_candidate_id,
        )


def test_build_does_not_mutate_the_session_or_graph() -> None:
    """The builder must read state without changing it."""

    session = _build_session(graph_version=7, active_node_ids=["seed", "scene-1"])
    session_graph = SessionGraph()
    session_id = session.session_id

    _add_node(
        session_graph,
        session_id=session_id,
        node_id="seed",
        node_kind=NodeKind.SEED,
        text="A seed sentence",
    )
    _add_node(
        session_graph,
        session_id=session_id,
        node_id="scene-1",
        node_kind=NodeKind.SCENE,
        text="A lone lantern burns in the rain.",
    )
    _add_edge(
        session_graph,
        session_id=session_id,
        edge_id="seed->scene-1",
        source_node_id="seed",
        target_node_id="scene-1",
        relation_type=RelationType.FOLLOWS,
    )

    before_session = session.model_dump(mode="python")
    before_nodes = {
        node_id: data["node"].text
        for node_id, data in session_graph.graph.nodes(data=True)
    }
    before_edges = sorted(
        (edge.edge_id, edge.source_node_id, edge.target_node_id)
        for _, _, _, edge_data in session_graph.graph.edges(keys=True, data=True)
        if isinstance((edge := edge_data.get("edge")), GraphEdge)
    )

    NarrativeContextBuilder().build(
        session=session,
        session_graph=session_graph,
        activation_candidate_id="scene-1",
    )

    assert session.model_dump(mode="python") == before_session
    assert {
        node_id: data["node"].text
        for node_id, data in session_graph.graph.nodes(data=True)
    } == before_nodes
    assert (
        sorted(
            (edge.edge_id, edge.source_node_id, edge.target_node_id)
            for _, _, _, edge_data in session_graph.graph.edges(keys=True, data=True)
            if isinstance((edge := edge_data.get("edge")), GraphEdge)
        )
        == before_edges
    )
