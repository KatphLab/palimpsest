"""Integration tests for fork-session isolation."""

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import GraphNode, SessionGraph
from models.commands import (
    CommandType,
    ForkSessionCommand,
    ForkSessionPayload,
    StartSessionCommand,
    StartSessionPayload,
)
from models.common import NodeKind
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime

pytestmark = pytest.mark.integration


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for fork-isolation tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


def _graph_signature(
    runtime: SessionRuntime,
) -> tuple[
    tuple[tuple[str, tuple[tuple[str, str], ...]], ...],
    tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...],
]:
    node_signature = tuple(
        sorted(
            (
                node_id,
                tuple(sorted((key, repr(value)) for key, value in node_data.items())),
            )
            for node_id, node_data in runtime.session_graph.graph.nodes(data=True)
        )
    )
    edge_signature = tuple(
        sorted(
            (
                source_node_id,
                target_node_id,
                edge_key,
                tuple(sorted((key, repr(value)) for key, value in edge_data.items())),
            )
            for source_node_id, target_node_id, edge_key, edge_data in runtime.session_graph.graph.edges(
                keys=True,
                data=True,
            )
        )
    )
    return node_signature, edge_signature


def test_fork_session_returns_new_session_and_independent_graph_state() -> None:
    """Forking should create a distinct session and isolate graph state."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    start_command = StartSessionCommand(
        command_id="cmd-start-fork-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(
            seed_text="A clockwork bird splits into two timelines."
        ),
    )
    start_result = runtime.handle_command(start_command)
    original_session_id = start_result.session_id
    original_graph = runtime.session_graph
    original_signature = _graph_signature(runtime)

    fork_command = ForkSessionCommand(
        command_id="cmd-fork-001",
        command_type=CommandType.FORK_SESSION,
        session_id=original_session_id,
        payload=ForkSessionPayload(fork_label="alternate branch"),
    )
    fork_result = runtime.handle_command(fork_command)
    fork_signature = _graph_signature(runtime)
    fork_session_id = fork_result.session_id

    assert original_session_id is not None
    assert fork_session_id is not None
    assert fork_session_id != original_session_id

    runtime.switch_session(fork_session_id)
    fork_graph = runtime.session_graph
    assert fork_graph is not original_graph

    fork_only_node_id = "fork-only-test-node"
    fork_graph.add_node(
        GraphNode(
            node_id=fork_only_node_id,
            session_id=fork_session_id,
            node_kind=NodeKind.SCENE,
            text="Fork-only node",
        )
    )

    runtime.switch_session(original_session_id)
    assert runtime.session_graph is original_graph

    assert start_result.accepted is True
    assert fork_result.accepted is True
    assert fork_signature != original_signature
    assert not original_graph.graph.has_node(fork_only_node_id)

    runtime.switch_session(fork_session_id)
    assert runtime.session_graph is fork_graph
    assert runtime.session_graph.graph.has_node(fork_only_node_id)
