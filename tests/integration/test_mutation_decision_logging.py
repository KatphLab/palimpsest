"""Integration tests for mutation decision telemetry logging."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from agents.llm_mutation_proposer import (
    LLMMutationProposer,
    LLMMutationProviderError,
)
from agents.scene_agent import SceneAgent
from config import setup_logging
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


class FlakyMutationProposalProvider:
    """Provider that fails once before returning a valid proposal."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            raise LLMMutationProviderError("synthetic mutation failure")

        return _mutation_response(prompt, decision_id="mutation-success-002")


def _narrative_context(prompt: str) -> dict[str, object]:
    """Extract the serialized narrative context from a proposer prompt."""

    context_text = prompt.rsplit("NarrativeContext: ", 1)[1]
    return cast(dict[str, object], json.loads(context_text))


def _mutation_response(prompt: str, *, decision_id: str) -> str:
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


def test_mutation_cycle_telemetry_reaches_console_and_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Mutation telemetry should be written to console and app.log."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "config.env.get_settings",
        lambda: SimpleNamespace(log_level="info", log_formatter="standard"),
    )

    setup_logging()

    proposal_provider = FlakyMutationProposalProvider()
    scene_provider = CountingSceneGenerationProvider()
    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=scene_provider),
        mutation_proposer=LLMMutationProposer(provider=proposal_provider),
    )
    runtime._mutation_cooldown = timedelta(milliseconds=0)
    runtime._global_mutation_storm_threshold = 1000

    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-telemetry-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(
                seed_text="A clockwork city turns one gear at a time."
            ),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None

    first_decision = runtime.advance_session_cycle()
    second_decision = runtime.advance_session_cycle()

    assert first_decision is not None
    assert first_decision.accepted is False
    assert second_decision is not None
    assert second_decision.accepted is True

    console_output = capsys.readouterr().out
    file_output = (tmp_path / "app.log").read_text()

    assert "mutation decision telemetry event=failed" in console_output
    assert "mutation decision telemetry event=applied" in console_output
    assert "mutation decision telemetry event=failed" in file_output
    assert "mutation decision telemetry event=applied" in file_output
    assert console_output.count("mutation decision telemetry event=failed") == 1
    assert console_output.count("mutation decision telemetry event=applied") == 1
    assert file_output.count("mutation decision telemetry event=failed") == 1
    assert file_output.count("mutation decision telemetry event=applied") == 1
