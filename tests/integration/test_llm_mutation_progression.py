"""Integration tests for LLM-driven mutation progression."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from typing import cast
from uuid import UUID

import pytest

from agents.llm_mutation_proposer import LLMMutationProposer
from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.common import MutationActionType
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


class SequencedMutationProposalProvider:
    """Deterministic LLM proposal provider for progression tests."""

    def __init__(self, responses: list[Callable[[str], str]]) -> None:
        self._responses = responses
        self.prompts: list[str] = []

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        index = len(self.prompts)
        if index >= len(self._responses):
            raise AssertionError("unexpected proposer call")

        self.prompts.append(prompt)
        return self._responses[index](prompt)


def _narrative_context(prompt: str) -> dict[str, object]:
    """Extract the serialized narrative context from a proposer prompt."""

    context_text = prompt.rsplit("NarrativeContext: ", 1)[1]
    return cast(dict[str, object], json.loads(context_text))


def _mutation_response(
    prompt: str,
    *,
    decision_id: str,
) -> str:
    """Build an add-node proposal from live narrative context."""

    context = _narrative_context(prompt)
    session_id = UUID(str(context["session_id"]))
    current_scene_node_id = str(context["current_scene_node_id"])

    return json.dumps(
        {
            "decision_id": decision_id,
            "session_id": str(session_id),
            "actor_node_id": current_scene_node_id,
            "target_ids": [current_scene_node_id],
            "action_type": MutationActionType.ADD_NODE.value,
            "risk_score": 0.25,
        }
    )


def test_repeated_continue_cycles_progress_beyond_two_scenes_with_llm_mutation() -> (
    None
):
    """Continue cycles should grow the story when the proposer stays LLM-driven."""

    proposal_provider = SequencedMutationProposalProvider(
        [
            lambda prompt: _mutation_response(prompt, decision_id="mutation-001"),
            lambda prompt: _mutation_response(prompt, decision_id="mutation-002"),
            lambda prompt: _mutation_response(prompt, decision_id="mutation-003"),
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
