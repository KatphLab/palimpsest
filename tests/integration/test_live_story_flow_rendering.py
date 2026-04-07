"""Integration tests for live story-flow rendering in the TUI."""

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
from tui.app import SessionApp

pytestmark = pytest.mark.integration


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for rendering tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


class SequencedMutationProposalProvider:
    """Deterministic LLM proposal provider for rendering tests."""

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
    action_type: MutationActionType,
) -> str:
    """Build a structured mutation proposal response from live context."""

    context = _narrative_context(prompt)
    session_id = UUID(str(context["session_id"]))
    previous_scene_node_id = str(context["previous_scene_node_id"])
    current_scene_node_id = str(context["current_scene_node_id"])

    if action_type is MutationActionType.ADD_NODE:
        target_ids = [current_scene_node_id]
    elif action_type is MutationActionType.REMOVE_EDGE:
        target_ids = [f"{previous_scene_node_id}->{current_scene_node_id}"]
    else:
        raise AssertionError(f"unsupported test action {action_type}")

    return json.dumps(
        {
            "decision_id": decision_id,
            "session_id": str(session_id),
            "actor_node_id": current_scene_node_id,
            "target_ids": target_ids,
            "action_type": action_type.value,
            "risk_score": 0.25,
        }
    )


def test_tui_panel_renders_growing_story_and_detached_nodes_after_edge_removal() -> (
    None
):
    """Panel output should reflect growth and later edge removals in story flow."""

    proposal_provider = SequencedMutationProposalProvider(
        [
            lambda prompt: _mutation_response(
                prompt,
                decision_id="mutation-cycle-001",
                action_type=MutationActionType.ADD_NODE,
            ),
            lambda prompt: _mutation_response(
                prompt,
                decision_id="mutation-cycle-002",
                action_type=MutationActionType.REMOVE_EDGE,
            ),
        ]
    )
    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
        mutation_proposer=LLMMutationProposer(provider=proposal_provider),
    )
    runtime._mutation_cooldown = timedelta(milliseconds=0)
    runtime._global_mutation_storm_threshold = 1000

    result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-live-story-flow-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A glass tower watches the sea."),
        )
    )
    assert result.accepted is True

    app = SessionApp(runtime=runtime)

    initial_panel = app._render_session_panel()
    assert "📖 STORY FLOW" in initial_panel
    assert "1. FIRST SCENE :: A glass tower watches the sea." in initial_panel

    first_decision = runtime.run_mutation_cycle()
    assert first_decision is not None
    assert first_decision.accepted is True
    assert first_decision.action_type is MutationActionType.ADD_NODE

    grown_panel = app._render_session_panel()
    assert "1. FIRST SCENE :: A glass tower watches the sea." in grown_panel
    assert (
        "  1.1 FIRST SCENE :: FIRST SCENE :: A glass tower watches the sea."
        in grown_panel
    )

    second_decision = runtime.run_mutation_cycle()
    assert second_decision is not None
    assert second_decision.accepted is True
    assert second_decision.action_type is MutationActionType.REMOVE_EDGE

    after_removal_panel = app._render_session_panel()
    assert "1. FIRST SCENE :: A glass tower watches the sea." in after_removal_panel
    assert "🧩 DETACHED SCENES" in after_removal_panel
    assert (
        "- FIRST SCENE :: FIRST SCENE :: A glass tower watches the sea."
        in after_removal_panel
    )
