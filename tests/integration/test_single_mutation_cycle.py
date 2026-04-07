"""Integration tests for one-mutation-per-cycle enforcement."""

from uuid import UUID

import pytest

from agents.mutation_agent import MutationAgent
from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.common import MutationActionType, NodeKind, RelationType
from models.graph import GraphEdge, GraphNode
from models.mutation import MutationProposal
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime

pytestmark = pytest.mark.integration


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for cycle-enforcement tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


def _start_running_session() -> tuple[SessionRuntime, UUID]:
    """Start a live session with deterministic scene bootstrapping."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-cycle-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(
                seed_text="A clockwork city turns one gear at a time."
            ),
        )
    )

    assert result.accepted is True
    assert result.session_id is not None
    return runtime, result.session_id


def _scene_node_id(runtime: SessionRuntime) -> str:
    """Return the bootstrapped scene node identifier."""

    for node_id, node_data in runtime.session_graph.graph.nodes(data=True):
        graph_node = node_data["node"]
        if isinstance(graph_node, GraphNode) and graph_node.node_kind is NodeKind.SCENE:
            return node_id

    raise AssertionError("bootstrap did not produce a scene node")


def _add_mutable_edge(
    session_graph: SessionGraph,
    *,
    session_id: UUID,
    source_node_id: str,
    branch_suffix: str,
) -> str:
    """Create an unlocked edge that autonomous mutation may remove."""

    target_node_id = f"{source_node_id}-{branch_suffix}"
    edge_id = f"{source_node_id}->{target_node_id}"
    session_graph.add_node(
        GraphNode(
            node_id=target_node_id,
            session_id=session_id,
            node_kind=NodeKind.SCENE,
            text=f"Branch scene {branch_suffix}",
        )
    )
    session_graph.add_edge(
        GraphEdge(
            edge_id=edge_id,
            session_id=session_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=RelationType.FOLLOWS,
            locked=False,
        )
    )
    return edge_id


def _remove_edge_proposal(
    *,
    session_id: UUID,
    actor_node_id: str,
    edge_id: str,
    decision_id: str,
) -> MutationProposal:
    """Build a deterministic remove-edge mutation proposal."""

    return MutationProposal(
        decision_id=decision_id,
        session_id=session_id,
        actor_node_id=actor_node_id,
        target_ids=[edge_id],
        action_type=MutationActionType.REMOVE_EDGE,
        risk_score=0.9,
    )


def test_single_mutation_cycle_rejects_second_mutation_review() -> None:
    """A single autonomous cycle review should reject a second mutation."""

    runtime, session_id = _start_running_session()
    scene_node_id = _scene_node_id(runtime)
    session_graph = runtime.session_graph

    first_edge_id = _add_mutable_edge(
        session_graph,
        session_id=session_id,
        source_node_id=scene_node_id,
        branch_suffix="branch-a",
    )
    second_edge_id = _add_mutable_edge(
        session_graph,
        session_id=session_id,
        source_node_id=scene_node_id,
        branch_suffix="branch-b",
    )

    agent = MutationAgent()

    first_decision = agent.review_proposal(
        _remove_edge_proposal(
            session_id=session_id,
            actor_node_id=scene_node_id,
            edge_id=first_edge_id,
            decision_id="mutation-cycle-001",
        ),
        session_graph,
    )
    agent.apply_decision(first_decision, session_graph)

    second_decision = agent.review_proposal(
        _remove_edge_proposal(
            session_id=session_id,
            actor_node_id=scene_node_id,
            edge_id=second_edge_id,
            decision_id="mutation-cycle-002",
        ),
        session_graph,
    )

    # First reviewed mutation is accepted and applied.
    assert first_decision.accepted is True
    assert session_graph.get_edge(first_edge_id) is None

    # Second mutation in the same cycle is rejected at review time.
    assert second_decision.accepted is False
    assert session_graph.get_edge(second_edge_id) is not None
