"""Dedicated LangGraph mutation proposer subgraph for US2."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import ConfigDict, Field

from graph.session_graph import SessionGraph
from models.common import NodeKind, StrictBaseModel, UTCDateTime
from models.session import Session

__all__ = ["MutationEngine"]

LOGGER = logging.getLogger(__name__)


class _ProposerStateModel(StrictBaseModel):
    """State carried through the mutation proposer subgraph."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    session: Session
    session_graph: SessionGraph
    activated_at: UTCDateTime
    activation_candidate_id: str | None = Field(default=None)


class MutationEngine:
    """Build and expose the dedicated mutation proposer subgraph."""

    def __init__(self) -> None:
        self._proposer_graph = self._build_proposer_graph()

    @property
    def proposer_graph(self) -> CompiledStateGraph[_ProposerStateModel]:
        """Return the compiled proposer graph."""

        return self._proposer_graph

    def build_proposer_subgraph(self) -> CompiledStateGraph[_ProposerStateModel]:
        """Return the compiled proposer graph."""

        return self._proposer_graph

    def select_activation_candidate(
        self,
        session: Session,
        session_graph: SessionGraph,
        *,
        activated_at: UTCDateTime | None = None,
    ) -> str | None:
        """Run the proposer subgraph and return a single activation candidate."""

        event_at = activated_at or datetime.now(timezone.utc)
        initial_state = _ProposerStateModel(
            session=session,
            session_graph=session_graph,
            activated_at=event_at,
        )
        final_state = _ProposerStateModel.model_validate(
            self._proposer_graph.invoke(initial_state)
        )
        return final_state.activation_candidate_id

    def _build_proposer_graph(self) -> CompiledStateGraph[_ProposerStateModel]:
        """Construct the single-node mutation proposer workflow."""

        LOGGER.debug("building dedicated mutation proposer subgraph")
        builder = StateGraph(_ProposerStateModel)
        builder.add_node(
            "select_activation_candidate", self._select_activation_candidate
        )
        builder.add_edge(START, "select_activation_candidate")
        builder.add_edge("select_activation_candidate", END)
        return builder.compile()

    def _select_activation_candidate(
        self, state: _ProposerStateModel
    ) -> _ProposerStateModel:
        """Select exactly one activation candidate from the live session graph."""

        activation_candidate_id = self._activation_candidate_id(state)
        if activation_candidate_id is None:
            LOGGER.debug("mutation proposer found no activation candidates")
        else:
            LOGGER.debug(
                "mutation proposer selected activation candidate %s",
                activation_candidate_id,
            )

        return state.model_copy(
            update={"activation_candidate_id": activation_candidate_id}
        )

    def _activation_candidate_id(self, state: _ProposerStateModel) -> str | None:
        """Return the single activation candidate for this cycle."""

        active_candidates = [
            node_id
            for node_id in state.session.active_node_ids
            if state.session_graph.graph.has_node(node_id)
        ]
        if active_candidates:
            for node_id in active_candidates:
                node_data = state.session_graph.graph.nodes[node_id]
                graph_node = node_data.get("node")
                if getattr(graph_node, "node_kind", None) is NodeKind.SEED:
                    continue

                return node_id

            return active_candidates[0]

        graph_node_ids = sorted(
            str(node_id) for node_id in state.session_graph.graph.nodes
        )
        if graph_node_ids:
            return graph_node_ids[0]

        return None
