"""Integration tests for live story-flow rendering in the TUI."""

from __future__ import annotations

from datetime import timedelta

import pytest

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


def test_tui_panel_renders_growing_story_and_detached_nodes_after_edge_removal() -> (
    None
):
    """Panel output should reflect growth and later edge removals in story flow."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
        refresh_interval_seconds=3600.0,
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
