"""Integration tests for mutation decision telemetry logging."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.llm_mutation_proposer import LLMMutationProposer
from agents.scene_agent import SceneAgent
from config import setup_logging
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from runtime.session_runtime import SessionRuntime
from tests.fixtures import (
    CountingSceneGenerationProvider,
    FlakyMutationProposalProvider,
)

pytestmark = pytest.mark.integration


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
