"""Shared test fixtures for scene generation and mutation proposal providers."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast
from uuid import UUID

from models.common import MutationActionType
from models.session import SceneGenerationProvider
from tests.fixtures.graph_instances import build_graph_instance

__all__ = [
    "CountingSceneGenerationProvider",
    "DeterministicSceneGenerationProvider",
    "FlakyMutationProposalProvider",
    "SequencedMutationProposalProvider",
    "build_graph_instance",
    "build_mutation_response",
    "extract_narrative_context",
]


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for runtime unit tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


class CountingSceneGenerationProvider(SceneGenerationProvider):
    """Scene provider that records how often generation is invoked."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate_first_scene(self, *, seed_text: str) -> str:
        self.call_count += 1
        return f"SCENE {self.call_count} :: {seed_text}"


class SequencedMutationProposalProvider:
    """Deterministic LLM proposal provider for runtime tests."""

    def __init__(self, responses: list[Callable[[str], str] | Exception]) -> None:
        self._responses = responses
        self.prompts: list[str] = []

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        index = len(self.prompts)
        if index >= len(self._responses):
            raise AssertionError("LLM proposer should not be called during backoff")

        self.prompts.append(prompt)
        response = self._responses[index]
        if isinstance(response, Exception):
            raise response

        return response(prompt)


class FlakyMutationProposalProvider:
    """Provider that fails once before returning a valid proposal."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        from agents.llm_mutation_proposer import LLMMutationProviderError

        self.calls += 1
        if self.calls == 1:
            raise LLMMutationProviderError("synthetic mutation failure")

        return build_mutation_response(prompt, decision_id="mutation-success-002")


def extract_narrative_context(prompt: str) -> dict[str, object]:
    """Extract the serialized narrative context from a proposer prompt."""

    context_text = prompt.rsplit("NarrativeContext: ", 1)[1]
    return cast(dict[str, object], json.loads(context_text))


def build_mutation_response(
    prompt: str,
    *,
    decision_id: str,
    action_type: MutationActionType = MutationActionType.ADD_NODE,
) -> str:
    """Build a structured mutation proposal response from live context."""

    context = extract_narrative_context(prompt)
    session_id = UUID(str(context["session_id"]))
    current_scene_node_id = str(context["current_scene_node_id"])

    if action_type is MutationActionType.ADD_NODE:
        target_ids = [current_scene_node_id]
    elif action_type is MutationActionType.REMOVE_EDGE:
        previous_scene_node_id = str(context["previous_scene_node_id"])
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
