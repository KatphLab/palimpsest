"""Tests for the LLM mutation proposer structured-output contract."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

import pytest

from agents.llm_mutation_proposer import (
    LLMMutationParseError,
    LLMMutationProposer,
    LLMMutationProviderError,
    LLMMutationSchemaError,
)
from models.common import MutationActionType
from models.narrative_context import NarrativeContext


def _module_path() -> Path:
    """Return the expected source path for the mutation proposer module."""

    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "agents"
        / "llm_mutation_proposer.py"
    )


class _LLMMutationProposerModule(Protocol):
    """Typed view of the mutation proposer module for mypy."""

    LLMMutationProposer: type[LLMMutationProposer]
    LLMMutationProviderError: type[LLMMutationProviderError]
    LLMMutationParseError: type[LLMMutationParseError]
    LLMMutationSchemaError: type[LLMMutationSchemaError]


def _load_module() -> _LLMMutationProposerModule:
    """Import the mutation proposer module once it exists."""

    module_path = _module_path()
    assert module_path.is_file(), (
        "agents.llm_mutation_proposer is missing; the structured-output mutation "
        "proposer has not been implemented yet"
    )

    from agents import llm_mutation_proposer

    return cast(_LLMMutationProposerModule, llm_mutation_proposer)


def _build_context() -> NarrativeContext:
    """Build a deterministic narrative context for proposer tests."""

    from models.narrative_context import (
        NarrativeContext,
        NarrativeGraphCounters,
        NarrativeSceneContext,
    )

    return NarrativeContext(
        session_id=UUID("11111111-1111-1111-1111-111111111111"),
        seed_node_id="seed-1",
        previous_scene_node_id="scene-1",
        current_scene_node_id="scene-2",
        last_two_scenes=[
            NarrativeSceneContext(
                scene_node_id="scene-1",
                scene_text="The lantern flickers.",
            ),
            NarrativeSceneContext(
                scene_node_id="scene-2",
                scene_text="The door opens.",
            ),
        ],
        graph_counters=NarrativeGraphCounters(
            graph_version=7,
            node_count=3,
            edge_count=2,
            active_node_count=2,
        ),
    )


class RecordingProposalProvider:
    """Deterministic provider double that records prompts and returns text."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.prompts: list[str] = []

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response_text


class FailingProposalProvider:
    """Provider double that simulates an unavailable LLM backend."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        self.prompts.append(prompt)
        raise RuntimeError("provider unavailable")


def test_llm_mutation_proposer_returns_validated_mutation_proposal() -> None:
    """A valid structured LLM response should produce a typed proposal."""

    module = _load_module()
    context = _build_context()
    provider = RecordingProposalProvider(
        "{"
        '"decision_id": "mutation-001", '
        '"session_id": "11111111-1111-1111-1111-111111111111", '
        '"actor_node_id": "scene-2", '
        '"target_ids": ["edge-1"], '
        '"action_type": "remove_edge", '
        '"risk_score": 0.75'
        "}"
    )

    proposer = module.LLMMutationProposer(provider=provider)
    proposal = proposer.propose(context)

    assert proposal.decision_id == "mutation-001"
    assert proposal.session_id == UUID("11111111-1111-1111-1111-111111111111")
    assert proposal.actor_node_id == "scene-2"
    assert proposal.target_ids == ["edge-1"]
    assert proposal.action_type is MutationActionType.REMOVE_EDGE
    assert proposal.risk_score == 0.75
    assert len(provider.prompts) == 1
    assert "scene-2" in provider.prompts[0]
    assert "11111111-1111-1111-1111-111111111111" in provider.prompts[0]


def test_llm_mutation_proposer_raises_provider_error_without_fallback() -> None:
    """Provider failures should surface as typed provider errors only."""

    module = _load_module()
    context = _build_context()
    provider = FailingProposalProvider()

    proposer = module.LLMMutationProposer(provider=provider)

    with pytest.raises(module.LLMMutationProviderError):
        proposer.propose(context)

    assert len(provider.prompts) == 1


def test_llm_mutation_proposer_raises_parse_error_for_non_json_content() -> None:
    """Non-JSON structured output should fail before schema validation."""

    module = _load_module()
    context = _build_context()
    provider = RecordingProposalProvider("not-json")

    proposer = module.LLMMutationProposer(provider=provider)

    with pytest.raises(module.LLMMutationParseError):
        proposer.propose(context)

    assert len(provider.prompts) == 1


def test_llm_mutation_proposer_raises_schema_error_for_invalid_payload() -> None:
    """JSON with the wrong shape should fail schema validation."""

    module = _load_module()
    context = _build_context()
    provider = RecordingProposalProvider(
        "{"
        '"decision_id": "mutation-002", '
        '"session_id": "11111111-1111-1111-1111-111111111111", '
        '"actor_node_id": "scene-2", '
        '"target_ids": ["edge-1"], '
        '"action_type": "remove_edge"'
        "}"
    )

    proposer = module.LLMMutationProposer(provider=provider)

    with pytest.raises(module.LLMMutationSchemaError):
        proposer.propose(context)

    assert len(provider.prompts) == 1
