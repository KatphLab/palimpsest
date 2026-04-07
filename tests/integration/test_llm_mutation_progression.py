"""Integration tests for LLM-driven mutation progression."""

from __future__ import annotations

from datetime import timedelta

import pytest

from agents.llm_mutation_proposer import LLMMutationProposer
from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.common import MutationActionType
from runtime.session_runtime import SessionRuntime
from tests.fixtures import (
    CountingSceneGenerationProvider,
    SequencedMutationProposalProvider,
    build_mutation_response,
)

pytestmark = pytest.mark.integration


def test_repeated_continue_cycles_progress_beyond_two_scenes_with_llm_mutation() -> (
    None
):
    """Continue cycles should grow the story when the proposer stays LLM-driven."""

    proposal_provider = SequencedMutationProposalProvider(
        [
            lambda prompt: build_mutation_response(prompt, decision_id="mutation-001"),
            lambda prompt: build_mutation_response(prompt, decision_id="mutation-002"),
            lambda prompt: build_mutation_response(prompt, decision_id="mutation-003"),
        ]
    )
    scene_provider = CountingSceneGenerationProvider()
    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=scene_provider),
        mutation_proposer=LLMMutationProposer(provider=proposal_provider),
    )
    runtime._mutation_cooldown = timedelta(milliseconds=0)
    runtime._global_mutation_storm_threshold = 1000

    result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-llm-progression-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(
                seed_text="A clockwork city turns one gear at a time."
            ),
        )
    )

    assert result.accepted is True
    assert runtime.session is not None

    decisions = [runtime.advance_session_cycle() for _ in range(3)]

    assert all(decision is not None for decision in decisions)
    assert all(decision.accepted for decision in decisions if decision is not None)
    assert all(
        decision.action_type is MutationActionType.ADD_NODE
        for decision in decisions
        if decision is not None
    )
    assert len(proposal_provider.prompts) == 3
    assert scene_provider.call_count == 4
    assert runtime.session_graph.graph.number_of_nodes() == 5
