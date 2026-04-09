"""Failing unit tests for the US2 mutation proposer subgraph."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from langchain_core.runnables.graph import Graph
from langgraph.graph import START
from langgraph.graph.state import CompiledStateGraph

from models.common import NodeKind, SessionStatus
from models.graph import GraphNode
from models.session import Session
from utils.time import utc_now

if TYPE_CHECKING:
    from agents.mutation_engine import MutationEngine
    from models.mutation import ProposerStateModel

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

    import models  # noqa: F401
    from agents.mutation_engine import MutationEngine

    return MutationEngine()


def _proposer_graph(engine: MutationEngine) -> CompiledStateGraph[ProposerStateModel]:
    """Return the compiled proposer graph exposed by the engine."""

    return engine.proposer_graph


def _graph_view(graph: CompiledStateGraph[ProposerStateModel]) -> Graph:
    """Return an inspectable graph view from LangGraph wrappers."""

    return graph.get_graph()


def _graph_node_names(graph: CompiledStateGraph[ProposerStateModel]) -> list[str]:
    """Collect node names from a graph or graph view."""

    view = _graph_view(graph)
    return list(view.nodes.keys())


def _start_successors(graph: CompiledStateGraph[ProposerStateModel]) -> list[str]:
    """Collect nodes that are activated directly from START."""

    view = _graph_view(graph)
    successors: list[str] = []
    for edge in view.edges:
        if edge.source == START:
            successors.append(edge.target)

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
    import models  # noqa: F401
    from graph.session_graph import SessionGraph

    session_graph = SessionGraph()
    seed_node_id = "seed-node-001"
    scene_node_id = "scene-node-001"
    session_graph.add_node(
        GraphNode(
            node_id=seed_node_id,
            session_id=session.session_id,
            node_kind=NodeKind.SEED,
            text=session.seed_text,
        )
    )
    session_graph.add_node(
        GraphNode(
            node_id=scene_node_id,
            session_id=session.session_id,
            node_kind=NodeKind.SCENE,
            text="The bell answers from beneath the surface.",
        )
    )
    session.active_node_ids = [seed_node_id, scene_node_id]

    engine = _mutation_engine()
    candidate_id = engine.select_activation_candidate(session, session_graph)

    assert candidate_id == scene_node_id
    assert candidate_id != seed_node_id
