"""Scene generation helpers for bootstrapping live narrative sessions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import ConfigDict

from config.env import get_settings
from graph.session_graph import SessionGraph
from models.common import (
    BudgetTelemetry,
    CheckStatus,
    CoherenceSnapshot,
    DriftCategory,
    NodeCoherenceScore,
    NodeKind,
    ProtectionReason,
    RelationType,
    SessionStatus,
    StrictBaseModel,
    TerminationVoteState,
    UTCDateTime,
)
from models.graph import GraphEdge, GraphNode
from models.node import SceneNode
from models.session import SceneGenerationProvider, Session

__all__ = ["SceneAgent"]

LOGGER = logging.getLogger(__name__)


class OpenAIChatSceneGenerationProvider(SceneGenerationProvider):
    """Generate first-scene text with ChatOpenAI."""

    def __init__(self, *, model_name: str | None = None) -> None:
        settings = get_settings()
        # mypy doesn't identify the correct parameters
        self._client = ChatOpenAI(
            model=model_name or settings.openai_model,  # type: ignore[call-arg]
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def generate_first_scene(self, *, seed_text: str) -> str:
        """Generate a narrative first scene from a seed prompt."""

        prompt = (
            "Write a vivid first scene for a narrative session based on this seed: "
            f"{seed_text}"
        )
        response = self._client.invoke(prompt)
        content = getattr(response, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("scene generation returned empty content")

        return content.strip()


class _BootstrapStateModel(StrictBaseModel):
    """State passed through the scene bootstrap graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    session: Session
    session_graph: SessionGraph
    activated_at: UTCDateTime
    seed_node_id: str | None = None
    scene_node_id: str | None = None
    seed_node: SceneNode | None = None
    scene_node: SceneNode | None = None
    first_scene_text: str | None = None


class SceneAgent:
    """Build and refresh the initial live narrative scene graph."""

    def __init__(self, provider: SceneGenerationProvider | None = None) -> None:
        self._provider = provider
        self._bootstrap_graph = self._build_bootstrap_graph()

    def bootstrap_session(
        self,
        session: Session,
        session_graph: SessionGraph,
        *,
        activated_at: UTCDateTime | None = None,
    ) -> tuple[str, str]:
        """Create the seed node and first scene for a new session."""

        event_at = activated_at or datetime.now(timezone.utc)
        initial_state = _BootstrapStateModel(
            session=session,
            session_graph=session_graph,
            activated_at=event_at,
        )
        final_state = _BootstrapStateModel.model_validate(
            self._bootstrap_graph.invoke(initial_state)
        )

        if final_state.seed_node_id is None or final_state.scene_node_id is None:
            raise RuntimeError("scene bootstrap did not produce node identifiers")

        return final_state.seed_node_id, final_state.scene_node_id

    def refresh_visible_state(
        self,
        session: Session,
        session_graph: SessionGraph,
        *,
        refreshed_at: UTCDateTime | None = None,
    ) -> None:
        """Refresh visible timestamps while the session is actively running."""

        if session.status != SessionStatus.RUNNING:
            return

        event_at = refreshed_at or datetime.now(timezone.utc)
        session.updated_at = event_at

        if session.coherence is not None:
            session.coherence.sampled_at = event_at

        if session.termination is not None:
            session.termination.last_updated_at = event_at

        for _, node_data in session_graph.graph.nodes(data=True):
            node_data["updated_at"] = event_at
            node_data["last_refreshed_at"] = event_at
            node_data["sampled_at"] = event_at

    def _build_bootstrap_graph(self) -> CompiledStateGraph[_BootstrapStateModel]:
        builder = StateGraph(_BootstrapStateModel)
        builder.add_node("create_seed_node", self._create_seed_node)
        builder.add_node("generate_first_scene", self._generate_first_scene)
        builder.add_edge(START, "create_seed_node")
        builder.add_edge("create_seed_node", "generate_first_scene")
        builder.add_edge("generate_first_scene", END)
        return builder.compile()

    def _create_seed_node(self, state: _BootstrapStateModel) -> _BootstrapStateModel:
        session = state.session
        event_at = state.activated_at
        seed_node_id = self._seed_node_id(session)
        scene_node_id = self._scene_node_id(session)

        session.status = SessionStatus.RUNNING
        session.created_at = event_at
        session.updated_at = event_at
        session.graph_version = 1
        session.coherence = self._build_coherence_snapshot(
            sampled_at=event_at,
            seed_node_id=seed_node_id,
            scene_node_id=scene_node_id,
        )
        session.budget = self._build_budget_snapshot()
        session.termination = self._build_termination_snapshot(event_at)

        seed_node = SceneNode(
            node_id=seed_node_id,
            session_id=session.session_id,
            node_kind=NodeKind.SEED,
            text=session.seed_text,
            entropy_score=0.0,
            activation_count=1,
            last_activated_at=event_at,
            is_seed_protected=True,
        )

        state.session_graph.add_node(
            GraphNode(
                node_id=seed_node.node_id,
                session_id=session.session_id,
                node_kind=seed_node.node_kind,
                text=seed_node.text,
            )
        )
        state.session_graph.graph.nodes[seed_node.node_id].update(
            {
                "scene_node": seed_node,
                "updated_at": event_at,
                "last_refreshed_at": event_at,
                "sampled_at": event_at,
            }
        )

        return state.model_copy(
            update={
                "seed_node_id": seed_node_id,
                "scene_node_id": scene_node_id,
                "seed_node": seed_node,
            }
        )

    def _generate_first_scene(
        self, state: _BootstrapStateModel
    ) -> _BootstrapStateModel:
        if state.seed_node_id is None or state.scene_node_id is None:
            raise RuntimeError("seed node identifiers must be set before generation")

        session = state.session
        event_at = state.activated_at
        first_scene_text = self._generation_provider().generate_first_scene(
            seed_text=session.seed_text
        )
        scene_node = SceneNode(
            node_id=state.scene_node_id,
            session_id=session.session_id,
            node_kind=NodeKind.SCENE,
            text=first_scene_text,
            entropy_score=0.18,
            drift_category=DriftCategory.STABLE,
            activation_count=1,
            last_activated_at=event_at,
        )

        state.session_graph.add_node(
            GraphNode(
                node_id=scene_node.node_id,
                session_id=session.session_id,
                node_kind=scene_node.node_kind,
                text=scene_node.text,
            )
        )
        state.session_graph.graph.nodes[scene_node.node_id].update(
            {
                "scene_node": scene_node,
                "updated_at": event_at,
                "last_refreshed_at": event_at,
                "sampled_at": event_at,
            }
        )
        state.session_graph.add_edge(
            GraphEdge(
                edge_id=self._seed_edge_id(state.seed_node_id, state.scene_node_id),
                session_id=session.session_id,
                source_node_id=state.seed_node_id,
                target_node_id=state.scene_node_id,
                relation_type=RelationType.FOLLOWS,
                locked=False,
                protected_reason=ProtectionReason.SEED,
            )
        )

        session.active_node_ids = [state.seed_node_id, state.scene_node_id]

        return state.model_copy(
            update={"scene_node": scene_node, "first_scene_text": first_scene_text}
        )

    def _generation_provider(self) -> SceneGenerationProvider:
        if self._provider is None:
            LOGGER.debug("creating default OpenAI scene generation provider")
            self._provider = OpenAIChatSceneGenerationProvider()

        return self._provider

    def _build_coherence_snapshot(
        self,
        *,
        sampled_at: UTCDateTime,
        seed_node_id: str,
        scene_node_id: str,
    ) -> CoherenceSnapshot:
        return CoherenceSnapshot(
            global_score=1.0,
            local_scores=[
                NodeCoherenceScore(
                    node_id=seed_node_id,
                    score=1.0,
                    sampled_at=sampled_at,
                ),
                NodeCoherenceScore(
                    node_id=scene_node_id,
                    score=0.95,
                    sampled_at=sampled_at,
                ),
            ],
            global_check_status=CheckStatus.PASS,
            sampled_at=sampled_at,
            checked_by="scene_agent",
        )

    def _build_budget_snapshot(self) -> BudgetTelemetry:
        return BudgetTelemetry(
            estimated_cost_usd=Decimal("0.00"),
            budget_limit_usd=Decimal("5.00"),
            token_input_count=0,
            token_output_count=0,
            model_call_count=0,
        )

    def _build_termination_snapshot(
        self, updated_at: UTCDateTime
    ) -> TerminationVoteState:
        return TerminationVoteState(
            active_node_count=2,
            votes_for_termination=0,
            votes_against_termination=2,
            majority_threshold=0.6,
            termination_reached=False,
            last_updated_at=updated_at,
        )

    def _seed_node_id(self, session: Session) -> str:
        return f"{session.session_id.hex[:8]}-seed"

    def _scene_node_id(self, session: Session) -> str:
        return f"{session.session_id.hex[:8]}-scene-1"

    def _seed_edge_id(self, seed_node_id: str, scene_node_id: str) -> str:
        return f"{seed_node_id}->{scene_node_id}"
