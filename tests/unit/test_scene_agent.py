"""Tests for scene bootstrap orchestration."""

from datetime import datetime, timezone
from uuid import UUID

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.common import SessionStatus
from models.node import SceneNode
from models.session import SceneGenerationProvider, Session


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for tests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_first_scene(self, *, seed_text: str) -> str:
        self.calls.append(seed_text)
        return f"FIRST SCENE :: {seed_text}"


def test_bootstrap_session_uses_injected_provider_and_builds_graph() -> None:
    """Bootstrap should create the seed, first scene, and connecting edge."""

    provider = DeterministicSceneGenerationProvider()
    scene_agent = SceneAgent(provider=provider)
    session_graph = SessionGraph()
    activated_at = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)
    session = Session(
        session_id=UUID(int=1),
        status=SessionStatus.CREATED,
        seed_text="A quiet room breathes in the dark.",
        graph_version=0,
        active_node_ids=[],
        created_at=activated_at,
        updated_at=activated_at,
    )

    seed_node_id, scene_node_id = scene_agent.bootstrap_session(
        session,
        session_graph,
        activated_at=activated_at,
    )

    assert provider.calls == [session.seed_text]
    assert seed_node_id == "00000000-seed"
    assert scene_node_id == "00000000-scene-1"
    assert session.status == SessionStatus.RUNNING
    assert session.graph_version == 1
    assert session.active_node_ids == [seed_node_id, scene_node_id]
    assert session.coherence is not None
    assert session.budget is not None
    assert session.termination is not None

    seed_node = session_graph.graph.nodes[seed_node_id]["scene_node"]
    scene_node = session_graph.graph.nodes[scene_node_id]["scene_node"]
    edge = session_graph.get_edge(f"{seed_node_id}->{scene_node_id}")

    assert isinstance(seed_node, SceneNode)
    assert seed_node.text == session.seed_text
    assert isinstance(scene_node, SceneNode)
    assert scene_node.text == f"FIRST SCENE :: {session.seed_text}"
    assert edge is not None
    assert session_graph.graph.number_of_nodes() == 2
