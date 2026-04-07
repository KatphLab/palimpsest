"""Integration tests for add-node mutation scene generation."""

import pytest

from agents.mutation_agent import MutationAgent
from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandType,
    ForkSessionCommand,
    ForkSessionPayload,
    StartSessionCommand,
    StartSessionPayload,
)
from models.common import MutationActionType
from models.mutation import MutationProposal
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime

pytestmark = pytest.mark.integration


class CountingSceneGenerationProvider(SceneGenerationProvider):
    """Scene provider that records how often generation is invoked."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate_first_scene(self, *, seed_text: str) -> str:
        self.call_count += 1
        return f"SCENE {self.call_count} :: {seed_text}"


def test_accepted_add_node_mutation_triggers_immediate_scene_generation() -> None:
    """Accepted add-node mutations should immediately generate the next scene."""

    provider = CountingSceneGenerationProvider()
    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=provider),
    )
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-add-node-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A lantern flickers in the hallway."),
        )
    )

    assert start_result.accepted is True
    assert start_result.session_id is not None
    assert runtime.session is not None

    active_scene_node_id = runtime.session.active_node_ids[-1]
    mutation_agent = MutationAgent()
    proposal = MutationProposal(
        decision_id="mutation-add-node-001",
        session_id=start_result.session_id,
        actor_node_id=active_scene_node_id,
        target_ids=[active_scene_node_id],
        action_type=MutationActionType.ADD_NODE,
        risk_score=0.25,
    )

    decision = mutation_agent.review_proposal(proposal, runtime.session_graph)

    assert decision.accepted is True

    mutation_agent.apply_decision(decision, runtime.session_graph)

    assert provider.call_count == 2
    assert runtime.session_graph.graph.number_of_nodes() == 3


def test_add_node_generation_remains_active_after_forking_session() -> None:
    """Forked sessions should retain add-node immediate generation hooks."""

    provider = CountingSceneGenerationProvider()
    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=provider),
    )
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-add-node-fork-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A hallway bends into two paths."),
        )
    )
    assert start_result.accepted is True
    assert start_result.session_id is not None

    fork_result = runtime.handle_command(
        ForkSessionCommand(
            command_id="cmd-fork-add-node-001",
            command_type=CommandType.FORK_SESSION,
            session_id=start_result.session_id,
            payload=ForkSessionPayload(fork_label="branch"),
        )
    )
    assert fork_result.accepted is True
    assert fork_result.session_id is not None

    runtime.switch_session(fork_result.session_id)
    assert runtime.session is not None

    active_scene_node_id = runtime.session.active_node_ids[-1]
    mutation_agent = MutationAgent()
    proposal = MutationProposal(
        decision_id="mutation-add-node-fork-001",
        session_id=fork_result.session_id,
        actor_node_id=active_scene_node_id,
        target_ids=[active_scene_node_id],
        action_type=MutationActionType.ADD_NODE,
        risk_score=0.2,
    )

    decision = mutation_agent.review_proposal(proposal, runtime.session_graph)
    assert decision.accepted is True
    mutation_agent.apply_decision(decision, runtime.session_graph)

    assert provider.call_count == 2
