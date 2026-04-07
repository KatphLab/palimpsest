"""Minimal US2 mutation review agent."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterable
from datetime import datetime, timezone

from graph.session_graph import SessionGraph
from models.common import (
    CheckStatus,
    MutationActionType,
    NodeKind,
    RelationType,
    SafetyCheckResult,
)
from models.graph import GraphEdge, GraphNode
from models.mutation import MutationDecision, MutationProposal
from models.node import SceneNode

__all__ = ["MutationAgent"]

LOGGER = logging.getLogger(__name__)


class MutationAgent:
    """Review mutation proposals and enforce locked-edge safety."""

    def review_proposal(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        """Return a deterministic decision for a mutation proposal."""

        if proposal.action_type is MutationActionType.NO_OP:
            return self._build_decision(
                proposal,
                accepted=True,
                safety_checks=[],
            )

        if proposal.action_type is MutationActionType.ADD_NODE:
            return self._review_add_node(proposal, session_graph)

        if proposal.action_type is MutationActionType.ADD_EDGE:
            return self._review_add_edge(proposal, session_graph)

        if proposal.action_type is MutationActionType.REMOVE_EDGE:
            return self._review_remove_edge(proposal, session_graph)

        if proposal.action_type is MutationActionType.REWRITE_NODE:
            return self._review_rewrite_node(proposal, session_graph)

        if proposal.action_type is MutationActionType.PRUNE_BRANCH:
            return self._review_prune_branch(proposal, session_graph)

        return self._build_decision(
            proposal,
            accepted=False,
            rejected_reason="unsupported mutation action",
            safety_checks=[
                SafetyCheckResult(
                    check_name="mutation_action_guard",
                    status=CheckStatus.FAIL,
                    message="mutation action is not supported",
                )
            ],
        )

    def apply_decision(
        self, decision: MutationDecision, session_graph: SessionGraph
    ) -> None:
        """Apply an accepted mutation decision to the owned graph."""

        if not decision.accepted:
            LOGGER.debug("skipping rejected mutation decision %s", decision.decision_id)
            return

        if decision.action_type is MutationActionType.NO_OP:
            return

        if decision.action_type is MutationActionType.ADD_NODE:
            self._apply_add_node(decision, session_graph)
            return

        if decision.action_type is MutationActionType.ADD_EDGE:
            self._apply_add_edge(decision, session_graph)
            return

        if decision.action_type is MutationActionType.REMOVE_EDGE:
            for edge_id in decision.target_ids:
                session_graph.remove_edge(edge_id)
            return

        if decision.action_type is MutationActionType.REWRITE_NODE:
            self._apply_rewrite_node(decision, session_graph)
            return

        if decision.action_type is MutationActionType.PRUNE_BRANCH:
            self._apply_prune_branch(decision, session_graph)
            return

        LOGGER.debug(
            "accepted mutation decision %s has unsupported action %s",
            decision.decision_id,
            decision.action_type,
        )

    def _review_add_node(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        anchor_node_id = self._anchor_node_id(proposal)
        anchor_node = self._require_node(session_graph, anchor_node_id)
        if anchor_node is None:
            return self._build_decision(
                proposal,
                accepted=False,
                rejected_reason="missing anchor node",
                safety_checks=[
                    SafetyCheckResult(
                        check_name="add_node_anchor_guard",
                        status=CheckStatus.FAIL,
                        message="anchor node is missing",
                    )
                ],
            )

        return self._build_decision(
            proposal,
            accepted=True,
            safety_checks=[
                SafetyCheckResult(
                    check_name="add_node_guard",
                    status=CheckStatus.PASS,
                    message=f"anchor node '{anchor_node_id}' is available",
                )
            ],
        )

    def _review_add_edge(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        source_node_id, target_node_id = self._edge_endpoints(proposal)
        source_node = self._require_node(session_graph, source_node_id)
        target_node = self._require_node(session_graph, target_node_id)

        if source_node is None or target_node is None:
            return self._build_decision(
                proposal,
                accepted=False,
                rejected_reason="missing edge endpoint",
                safety_checks=[
                    SafetyCheckResult(
                        check_name="add_edge_endpoint_guard",
                        status=CheckStatus.FAIL,
                        message="source or target node is missing",
                    )
                ],
            )

        return self._build_decision(
            proposal,
            accepted=True,
            safety_checks=[
                SafetyCheckResult(
                    check_name="add_edge_guard",
                    status=CheckStatus.PASS,
                    message=(
                        f"edge can connect '{source_node_id}' to '{target_node_id}'"
                    ),
                )
            ],
        )

    def _review_remove_edge(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        for edge_id in proposal.target_ids:
            edge = session_graph.get_edge(edge_id)
            if edge is None:
                return self._build_decision(
                    proposal,
                    accepted=False,
                    rejected_reason="missing edge",
                    safety_checks=[
                        SafetyCheckResult(
                            check_name="edge_exists_guard",
                            status=CheckStatus.FAIL,
                            message="edge is missing",
                        )
                    ],
                )

            if edge.locked:
                return self._build_decision(
                    proposal,
                    accepted=False,
                    rejected_reason="locked edge",
                    safety_checks=[
                        SafetyCheckResult(
                            check_name="locked_edge_guard",
                            status=CheckStatus.FAIL,
                            message="edge is locked",
                        )
                    ],
                )

            if edge.protected_reason is not None:
                return self._build_decision(
                    proposal,
                    accepted=False,
                    rejected_reason="protected edge",
                    safety_checks=[
                        SafetyCheckResult(
                            check_name="protected_edge_guard",
                            status=CheckStatus.FAIL,
                            message="edge is protected",
                        )
                    ],
                )

        if proposal.target_ids:
            safety_checks = [
                SafetyCheckResult(
                    check_name="edge_mutable_check",
                    status=CheckStatus.PASS,
                    message="edge is unlocked",
                )
                for _ in proposal.target_ids
            ]
        else:
            safety_checks = [
                SafetyCheckResult(
                    check_name="edge_mutable_check",
                    status=CheckStatus.PASS,
                    message="no edge targets provided",
                )
            ]

        return self._build_decision(
            proposal,
            accepted=True,
            safety_checks=safety_checks,
        )

    def _review_rewrite_node(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        node_id = self._node_target_id(proposal)
        node = self._require_node(session_graph, node_id)
        if node is None:
            return self._build_decision(
                proposal,
                accepted=False,
                rejected_reason="missing node",
                safety_checks=[
                    SafetyCheckResult(
                        check_name="rewrite_node_guard",
                        status=CheckStatus.FAIL,
                        message="node is missing",
                    )
                ],
            )

        if self._is_protected_node(node):
            return self._build_decision(
                proposal,
                accepted=False,
                rejected_reason="protected node",
                safety_checks=[
                    SafetyCheckResult(
                        check_name="rewrite_node_guard",
                        status=CheckStatus.FAIL,
                        message="node is protected",
                    )
                ],
            )

        return self._build_decision(
            proposal,
            accepted=True,
            safety_checks=[
                SafetyCheckResult(
                    check_name="rewrite_node_guard",
                    status=CheckStatus.PASS,
                    message=f"node '{node_id}' can be rewritten",
                )
            ],
        )

    def _review_prune_branch(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        root_node_id = self._node_target_id(proposal)
        root_node = self._require_node(session_graph, root_node_id)
        if root_node is None:
            return self._build_decision(
                proposal,
                accepted=False,
                rejected_reason="missing branch root",
                safety_checks=[
                    SafetyCheckResult(
                        check_name="prune_branch_root_guard",
                        status=CheckStatus.FAIL,
                        message="branch root is missing",
                    )
                ],
            )

        branch_node_ids = self._collect_branch_node_ids(session_graph, root_node_id)
        protected_reason = self._branch_protection_reason(
            session_graph, branch_node_ids
        )
        if protected_reason is not None:
            return self._build_decision(
                proposal,
                accepted=False,
                rejected_reason=protected_reason,
                safety_checks=[
                    SafetyCheckResult(
                        check_name="prune_branch_guard",
                        status=CheckStatus.FAIL,
                        message="branch contains protected state",
                    )
                ],
            )

        return self._build_decision(
            proposal,
            accepted=True,
            safety_checks=[
                SafetyCheckResult(
                    check_name="prune_branch_guard",
                    status=CheckStatus.PASS,
                    message=f"branch rooted at '{root_node_id}' can be pruned",
                )
            ],
        )

    def _apply_add_node(
        self, decision: MutationDecision, session_graph: SessionGraph
    ) -> None:
        anchor_node_id = self._anchor_node_id(decision)
        anchor_node = self._require_node(session_graph, anchor_node_id)
        if anchor_node is None:
            raise ValueError(f"anchor node '{anchor_node_id}' does not exist")

        node_data = session_graph.graph.nodes[anchor_node_id]
        anchor_scene_node = node_data.get("scene_node")
        anchor_text = (
            anchor_scene_node.text
            if isinstance(anchor_scene_node, SceneNode)
            else anchor_node.text
        )
        new_node_id = self._unique_node_id(
            session_graph,
            f"{anchor_node_id}-{decision.decision_id}-node",
        )
        generated_text = f"{anchor_text} :: {decision.decision_id}"
        activated_at = datetime.now(timezone.utc)

        session_graph.add_node(
            GraphNode(
                node_id=new_node_id,
                session_id=anchor_node.session_id,
                node_kind=NodeKind.SCENE,
                text=generated_text,
            )
        )
        session_graph.graph.nodes[new_node_id].update(
            {
                "scene_node": SceneNode(
                    node_id=new_node_id,
                    session_id=anchor_node.session_id,
                    node_kind=NodeKind.SCENE,
                    text=generated_text,
                    entropy_score=0.35,
                    activation_count=1,
                    last_activated_at=activated_at,
                ),
                "updated_at": activated_at,
                "last_refreshed_at": activated_at,
                "sampled_at": activated_at,
            }
        )
        session_graph.add_edge(
            GraphEdge(
                edge_id=f"{anchor_node_id}->{new_node_id}",
                session_id=anchor_node.session_id,
                source_node_id=anchor_node_id,
                target_node_id=new_node_id,
                relation_type=RelationType.BRANCHES_FROM,
            )
        )

    def _apply_add_edge(
        self, decision: MutationDecision, session_graph: SessionGraph
    ) -> None:
        source_node_id, target_node_id = self._edge_endpoints(decision)
        source_node = self._require_node(session_graph, source_node_id)
        if source_node is None:
            raise ValueError(f"source node '{source_node_id}' does not exist")

        target_node = self._require_node(session_graph, target_node_id)
        if target_node is None:
            raise ValueError(f"target node '{target_node_id}' does not exist")

        session_graph.add_edge(
            GraphEdge(
                edge_id=f"{source_node_id}->{target_node_id}",
                session_id=source_node.session_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relation_type=RelationType.FOLLOWS,
            )
        )

    def _apply_rewrite_node(
        self, decision: MutationDecision, session_graph: SessionGraph
    ) -> None:
        node_id = self._node_target_id(decision)
        node = self._require_node(session_graph, node_id)
        if node is None:
            raise ValueError(f"node '{node_id}' does not exist")

        node_data = session_graph.graph.nodes[node_id]
        scene_node = node_data.get("scene_node")
        rewritten_text = f"{node.text} :: rewritten {decision.decision_id}"

        session_graph.graph.nodes[node_id]["node"] = node.model_copy(
            update={"text": rewritten_text}
        )
        if isinstance(scene_node, SceneNode):
            session_graph.graph.nodes[node_id]["scene_node"] = scene_node.model_copy(
                update={"text": rewritten_text}
            )

        updated_at = datetime.now(timezone.utc)
        session_graph.graph.nodes[node_id]["updated_at"] = updated_at
        session_graph.graph.nodes[node_id]["last_refreshed_at"] = updated_at
        session_graph.graph.nodes[node_id]["sampled_at"] = updated_at

    def _apply_prune_branch(
        self, decision: MutationDecision, session_graph: SessionGraph
    ) -> None:
        root_node_id = self._node_target_id(decision)
        branch_node_ids = self._collect_branch_node_ids(session_graph, root_node_id)
        session_graph.graph.remove_nodes_from(branch_node_ids)

    def _anchor_node_id(self, proposal: MutationProposal) -> str:
        if proposal.target_ids:
            return proposal.target_ids[0]

        return proposal.actor_node_id

    def _node_target_id(self, proposal: MutationProposal) -> str:
        return self._anchor_node_id(proposal)

    def _edge_endpoints(self, proposal: MutationProposal) -> tuple[str, str]:
        if len(proposal.target_ids) >= 2:
            return proposal.target_ids[0], proposal.target_ids[1]

        if proposal.target_ids:
            return proposal.actor_node_id, proposal.target_ids[0]

        raise ValueError("edge mutations require at least one target node")

    def _collect_branch_node_ids(
        self, session_graph: SessionGraph, root_node_id: str
    ) -> list[str]:
        node_ids: list[str] = []
        visited: set[str] = set()
        pending: deque[str] = deque([root_node_id])

        while pending:
            node_id = pending.popleft()
            if node_id in visited:
                continue

            visited.add(node_id)
            if not session_graph.graph.has_node(node_id):
                continue

            node_ids.append(node_id)
            for target_node_id in self._branch_children(session_graph, node_id):
                if target_node_id not in visited:
                    pending.append(target_node_id)

        return node_ids

    def _branch_children(self, session_graph: SessionGraph, node_id: str) -> list[str]:
        child_node_ids: list[str] = []
        for _, target_node_id, _, edge_data in session_graph.graph.out_edges(
            node_id, keys=True, data=True
        ):
            edge = edge_data.get("edge") if isinstance(edge_data, dict) else None
            if not isinstance(edge, GraphEdge):
                continue

            if edge.relation_type is RelationType.BRANCHES_FROM:
                child_node_ids.append(target_node_id)

        return child_node_ids

    def _branch_protection_reason(
        self, session_graph: SessionGraph, node_ids: list[str]
    ) -> str | None:
        for node_id in node_ids:
            node_reason = self._branch_node_protection_reason(session_graph, node_id)
            if node_reason is not None:
                return node_reason

            edge_reason = self._branch_edge_protection_reason(session_graph, node_id)
            if edge_reason is not None:
                return edge_reason

        return None

    def _branch_node_protection_reason(
        self, session_graph: SessionGraph, node_id: str
    ) -> str | None:
        node_data = self._node_data(session_graph, node_id)
        if node_data is None:
            return "missing branch node"

        raw_node = node_data.get("node")
        node_to_check = (
            raw_node if isinstance(raw_node, (GraphNode, SceneNode)) else None
        )
        if self._is_protected_node(node_to_check):
            return "protected node"

        return None

    def _branch_edge_protection_reason(
        self, session_graph: SessionGraph, node_id: str
    ) -> str | None:
        edge_views = (
            session_graph.graph.out_edges(node_id, keys=True, data=True),
            session_graph.graph.in_edges(node_id, keys=True, data=True),
        )
        for edge_view in edge_views:
            reason = self._edge_view_protection_reason(edge_view)
            if reason is not None:
                return reason

        return None

    def _edge_view_protection_reason(
        self, edge_view: Iterable[tuple[object, object, object, object]]
    ) -> str | None:
        for _, _, _, edge_data in edge_view:
            edge = edge_data.get("edge") if isinstance(edge_data, dict) else None
            if not isinstance(edge, GraphEdge):
                continue

            if edge.locked:
                return "locked edge"

            if edge.protected_reason is not None:
                return "protected edge"

        return None

    def _require_node(
        self, session_graph: SessionGraph, node_id: str
    ) -> GraphNode | None:
        node_data = self._node_data(session_graph, node_id)
        if node_data is None:
            return None

        node = node_data.get("node")
        return node if isinstance(node, GraphNode) else None

    def _node_data(
        self, session_graph: SessionGraph, node_id: str
    ) -> dict[str, object] | None:
        if not session_graph.graph.has_node(node_id):
            return None

        node_data = session_graph.graph.nodes[node_id]
        return node_data if isinstance(node_data, dict) else None

    def _is_protected_node(self, node: GraphNode | SceneNode | None) -> bool:
        if node is None:
            return False

        if isinstance(node, SceneNode):
            return node.is_seed_protected or node.node_kind is NodeKind.SEED

        return node.node_kind is NodeKind.SEED

    def _unique_node_id(self, session_graph: SessionGraph, base_node_id: str) -> str:
        candidate = base_node_id
        suffix = 1
        while session_graph.graph.has_node(candidate):
            candidate = f"{base_node_id}-{suffix}"
            suffix += 1

        return candidate

    def _build_decision(
        self,
        proposal: MutationProposal,
        *,
        accepted: bool,
        safety_checks: list[SafetyCheckResult],
        rejected_reason: str | None = None,
    ) -> MutationDecision:
        decision_data = proposal.model_dump(mode="python")
        decision_data.update(
            {
                "accepted": accepted,
                "safety_checks": safety_checks,
                "rejected_reason": rejected_reason,
            }
        )
        return MutationDecision.model_validate(decision_data)
