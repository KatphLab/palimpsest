"""Failing unit tests for the US2 mutation proposer subgraph."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from langgraph.graph import START

from agents.mutation_engine import MutationEngine
from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.common import SessionStatus
from models.session import Session
from tests.fixtures import DeterministicSceneGenerationProvider
from utils.time import utc_now

_SCENE_AGENT_NODE_NAMES = {"create_seed_node", "generate_first_scene"}


def _mutation_engine_module_path() -> Path:
    """Return the expected source path for the mutation engine module."""

    return Path(__file__).resolve().parents[2] / "src" / "agents" / "mutation_engine.py"


def _mutation_engine() -> MutationEngine:
    """Import the mutation engine once its module exists."""

    module_path = _mutation_engine_module_path()
    assert module_path.is_file(), (
        "agents.mutation_engine is missing; the dedicated mutation proposer "
        "subgraph has not been implemented yet"
    )

    return MutationEngine()


def _proposer_graph(engine: object) -> object:
    """Resolve the compiled proposer graph from the engine."""

    for attr_name in ("proposer_graph", "_proposer_graph"):
        graph = getattr(engine, attr_name, None)
        if graph is not None:
            return graph

    for method_name in ("build_proposer_subgraph", "_build_proposer_graph"):
        builder = getattr(engine, method_name, None)
        if callable(builder):
            return builder()

    raise AssertionError("MutationEngine does not expose a proposer subgraph builder")


def _graph_view(graph: object) -> object:
    """Return an inspectable graph view from LangGraph wrappers."""

    getter = getattr(graph, "get_graph", None)
    if callable(getter):
        return getter()

    return graph


def _graph_node_names(graph: object) -> list[str]:
    """Collect node names from a graph or graph view."""

    view = _graph_view(graph)
    nodes = getattr(view, "nodes", None)
    assert nodes is not None, "mutation proposer graph cannot be inspected for nodes"

    if hasattr(nodes, "keys"):
        return list(nodes.keys())

    return list(nodes)


def _start_successors(graph: object) -> list[str]:
    """Collect nodes that are activated directly from START."""

    view = _graph_view(graph)
    edges = getattr(view, "edges", None)
    assert edges is not None, "mutation proposer graph cannot be inspected for edges"

    successors: list[str] = []
    for edge in edges:
        if len(edge) >= 2 and edge[0] == START:
            successors.append(edge[1])

    return successors


def test_mutation_engine_proposer_subgraph_has_single_start_activation() -> None:
    """The proposer subgraph should activate exactly one node from START."""

    engine = _mutation_engine()
    graph = _proposer_graph(engine)
    start_successors = _start_successors(graph)

    assert len(start_successors) == 1, (
        "mutation proposer subgraph should have a single START successor, "
        f"found {start_successors!r}"
    )


def test_mutation_engine_proposer_subgraph_isolated_from_scene_generation() -> None:
    """The proposer subgraph should not reuse scene-bootstrap nodes."""

    engine = _mutation_engine()
    graph = _proposer_graph(engine)
    node_names = set(_graph_node_names(graph))

    assert _SCENE_AGENT_NODE_NAMES.isdisjoint(node_names), (
        "mutation proposer subgraph should not include scene-generation nodes, "
        f"found {_SCENE_AGENT_NODE_NAMES & node_names!r}"
    )


def test_mutation_engine_prefers_scene_activation_candidate_when_available() -> None:
    """The proposer should choose an active scene node before a seed node."""

    session = Session(
        session_id=uuid4(),
        status=SessionStatus.CREATED,
        seed_text="A bell tolls under black water.",
        graph_version=0,
        active_node_ids=[],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session_graph = SessionGraph()
    scene_agent = SceneAgent(provider=DeterministicSceneGenerationProvider())
    seed_node_id, scene_node_id = scene_agent.bootstrap_session(session, session_graph)

    engine = _mutation_engine()
    candidate_id = engine.select_activation_candidate(session, session_graph)

    assert candidate_id == scene_node_id
    assert candidate_id != seed_node_id
