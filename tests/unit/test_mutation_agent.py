"""Tests for the minimal US2 mutation agent."""

from uuid import UUID

from agents.mutation_agent import MutationAgent
from graph.session_graph import SessionGraph
from models.common import (
    CheckStatus,
    MutationActionType,
    NodeKind,
    ProtectionReason,
    RelationType,
    SafetyCheckResult,
)
from models.graph import GraphEdge, GraphNode
from models.mutation import MutationProposal


def _session_graph(
    *, locked: bool, protected_reason: ProtectionReason | None = None
) -> tuple[SessionGraph, str]:
    """Build a graph with one removable edge."""

    graph = SessionGraph()
    session_id = UUID(int=1)
    source = GraphNode(
        node_id="node-a",
        session_id=session_id,
        node_kind=NodeKind.SEED,
        text="seed",
    )
    target = GraphNode(
        node_id="node-b",
        session_id=session_id,
        node_kind=NodeKind.SCENE,
        text="scene",
    )
    edge = GraphEdge(
        edge_id="edge-1",
        session_id=session_id,
        source_node_id=source.node_id,
        target_node_id=target.node_id,
        relation_type=RelationType.FOLLOWS,
        locked=locked,
        protected_reason=protected_reason
        if protected_reason is not None
        else (ProtectionReason.USER_LOCK if locked else None),
    )

    graph.add_node(source)
    graph.add_node(target)
    graph.add_edge(edge)
    return graph, edge.edge_id


def _remove_edge_proposal(edge_id: str) -> MutationProposal:
    """Build a deterministic remove-edge proposal."""

    return MutationProposal(
        decision_id="mutation-001",
        session_id=UUID("11111111-1111-1111-1111-111111111111"),
        actor_node_id="node-a",
        target_ids=[edge_id],
        action_type=MutationActionType.REMOVE_EDGE,
        risk_score=0.9,
    )


def test_mutation_agent_blocks_locked_edge_removal() -> None:
    """Locked edges must be rejected by the mutation safety filter."""

    graph, edge_id = _session_graph(locked=True)
    agent = MutationAgent()

    decision = agent.review_proposal(_remove_edge_proposal(edge_id), graph)

    assert decision.accepted is False
    assert decision.rejected_reason == "locked edge"
    assert decision.safety_checks == [
        SafetyCheckResult(
            check_name="locked_edge_guard",
            status=CheckStatus.FAIL,
            message="edge is locked",
        )
    ]

    agent.apply_decision(decision, graph)

    assert graph.get_edge(edge_id) is not None

    repeated = agent.review_proposal(_remove_edge_proposal(edge_id), graph)
    assert repeated.model_dump(mode="python") == decision.model_dump(mode="python")


def test_mutation_agent_removes_unlocked_edge_when_accepted() -> None:
    """Unlocked edges should be removable after a successful review."""

    graph, edge_id = _session_graph(locked=False)
    agent = MutationAgent()

    decision = agent.review_proposal(_remove_edge_proposal(edge_id), graph)

    assert decision.accepted is True
    assert decision.rejected_reason is None
    assert decision.safety_checks == [
        SafetyCheckResult(
            check_name="edge_mutable_check",
            status=CheckStatus.PASS,
            message="edge is unlocked",
        )
    ]

    agent.apply_decision(decision, graph)

    assert graph.get_edge(edge_id) is None


def test_mutation_agent_blocks_seed_protected_edge_removal() -> None:
    """Seed-protected edges must be rejected by the mutation safety filter."""

    graph, edge_id = _session_graph(
        locked=False, protected_reason=ProtectionReason.SEED
    )
    agent = MutationAgent()

    decision = agent.review_proposal(_remove_edge_proposal(edge_id), graph)

    assert decision.accepted is False
    assert decision.rejected_reason == "protected edge"
    assert decision.safety_checks == [
        SafetyCheckResult(
            check_name="protected_edge_guard",
            status=CheckStatus.FAIL,
            message="edge is protected",
        )
    ]

    agent.apply_decision(decision, graph)

    assert graph.get_edge(edge_id) is not None
