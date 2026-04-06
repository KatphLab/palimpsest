"""Minimal US2 mutation review agent."""

from __future__ import annotations

import logging

from graph.session_graph import SessionGraph
from models.common import CheckStatus, MutationActionType, SafetyCheckResult
from models.mutation import MutationDecision, MutationProposal

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

        if proposal.action_type is MutationActionType.REMOVE_EDGE:
            return self._review_remove_edge(proposal, session_graph)

        return self._build_decision(
            proposal,
            accepted=True,
            safety_checks=[
                SafetyCheckResult(
                    check_name="mutation_guard",
                    status=CheckStatus.PASS,
                    message="mutation permitted",
                )
            ],
        )

    def filter_proposal(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        """Compatibility alias for review_proposal()."""

        return self.review_proposal(proposal, session_graph)

    def evaluate_proposal(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        """Compatibility alias for review_proposal()."""

        return self.review_proposal(proposal, session_graph)

    def decide(
        self, proposal: MutationProposal, session_graph: SessionGraph
    ) -> MutationDecision:
        """Compatibility alias for review_proposal()."""

        return self.review_proposal(proposal, session_graph)

    def apply_decision(
        self, decision: MutationDecision, session_graph: SessionGraph
    ) -> None:
        """Apply an accepted mutation decision to the owned graph."""

        if not decision.accepted:
            LOGGER.debug("skipping rejected mutation decision %s", decision.decision_id)
            return

        if decision.action_type is not MutationActionType.REMOVE_EDGE:
            return

        for edge_id in decision.target_ids:
            session_graph.remove_edge(edge_id)

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
                    check_name="locked_edge_guard",
                    status=CheckStatus.PASS,
                    message="edge is unlocked",
                )
                for _ in proposal.target_ids
            ]
        else:
            safety_checks = [
                SafetyCheckResult(
                    check_name="locked_edge_guard",
                    status=CheckStatus.PASS,
                    message="no edge targets provided",
                )
            ]

        return self._build_decision(
            proposal,
            accepted=True,
            safety_checks=safety_checks,
        )

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
