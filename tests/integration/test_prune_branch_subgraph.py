"""Integration tests for prune-branch subgraph removal."""

from uuid import UUID

import pytest

from agents.mutation_agent import MutationAgent
from graph.session_graph import SessionGraph
from models.common import MutationActionType, NodeKind, ProtectionReason, RelationType
from models.graph import GraphEdge, GraphNode
from models.mutation import MutationProposal

pytestmark = pytest.mark.integration

_SESSION_ID = UUID(int=1)


def _branch_graph(
    *, protected_leaf_edge: bool
) -> tuple[SessionGraph, tuple[str, str, str]]:
    """Build a small branch-shaped graph for prune-branch assertions."""

    graph = SessionGraph()
    root_node = GraphNode(
        node_id="branch-root",
        session_id=_SESSION_ID,
        node_kind=NodeKind.SCENE,
        text="branch root",
    )
    child_node = GraphNode(
        node_id="branch-child",
        session_id=_SESSION_ID,
        node_kind=NodeKind.SCENE,
        text="branch child",
    )
    leaf_node = GraphNode(
        node_id="branch-leaf",
        session_id=_SESSION_ID,
        node_kind=NodeKind.SCENE,
        text="branch leaf",
    )

    graph.add_node(root_node)
    graph.add_node(child_node)
    graph.add_node(leaf_node)

    graph.add_edge(
        GraphEdge(
            edge_id="edge-root-child",
            session_id=_SESSION_ID,
            source_node_id=root_node.node_id,
            target_node_id=child_node.node_id,
            relation_type=RelationType.BRANCHES_FROM,
        )
    )
    graph.add_edge(
        GraphEdge(
            edge_id="edge-child-leaf",
            session_id=_SESSION_ID,
            source_node_id=child_node.node_id,
            target_node_id=leaf_node.node_id,
            relation_type=RelationType.BRANCHES_FROM,
            protected_reason=(
                ProtectionReason.SAFETY_GUARD if protected_leaf_edge else None
            ),
        )
    )

    return graph, (root_node.node_id, child_node.node_id, leaf_node.node_id)


def _prune_branch_proposal(root_node_id: str) -> MutationProposal:
    """Build a prune-branch proposal for the given branch root."""

    return MutationProposal(
        decision_id="mutation-prune-001",
        session_id=_SESSION_ID,
        actor_node_id=root_node_id,
        target_ids=[root_node_id],
        action_type=MutationActionType.PRUNE_BRANCH,
        risk_score=0.9,
    )


def test_prune_branch_removes_the_full_unprotected_subgraph() -> None:
    """Pruning a clean branch should delete the entire reachable subgraph."""

    graph, node_ids = _branch_graph(protected_leaf_edge=False)
    agent = MutationAgent()

    decision = agent.review_proposal(_prune_branch_proposal(node_ids[0]), graph)

    assert decision.accepted is True

    agent.apply_decision(decision, graph)

    assert graph.graph.number_of_nodes() == 0
    assert graph.graph.number_of_edges() == 0


def test_prune_branch_rejects_when_the_branch_contains_protected_state() -> None:
    """Pruning must refuse branches that include protected descendants."""

    graph, node_ids = _branch_graph(protected_leaf_edge=True)
    agent = MutationAgent()

    decision = agent.review_proposal(_prune_branch_proposal(node_ids[0]), graph)

    assert decision.accepted is False


def test_prune_branch_does_not_remove_non_branch_relations() -> None:
    """Prune traversal should stay on BRANCHES_FROM edges only."""

    graph, node_ids = _branch_graph(protected_leaf_edge=False)
    external_node = GraphNode(
        node_id="external-node",
        session_id=_SESSION_ID,
        node_kind=NodeKind.SCENE,
        text="external",
    )
    graph.add_node(external_node)
    graph.add_edge(
        GraphEdge(
            edge_id="edge-child-external",
            session_id=_SESSION_ID,
            source_node_id=node_ids[1],
            target_node_id=external_node.node_id,
            relation_type=RelationType.REINFORCES,
        )
    )

    agent = MutationAgent()
    decision = agent.review_proposal(_prune_branch_proposal(node_ids[0]), graph)
    assert decision.accepted is True

    agent.apply_decision(decision, graph)

    assert graph.graph.has_node(external_node.node_id)
    assert graph.graph.number_of_nodes() == 1
