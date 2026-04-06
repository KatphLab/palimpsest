"""Integration tests for live refresh freshness."""

from datetime import datetime, timezone
from time import sleep

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime

pytestmark = pytest.mark.integration

_REFRESH_TIMESTAMP_KEYS = ("updated_at", "last_refreshed_at", "sampled_at")


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for refresh tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


def _latest_refresh_timestamp(runtime: SessionRuntime) -> datetime:
    timestamps: list[datetime] = []
    for _, data in runtime.session_graph.graph.nodes(data=True):
        for key in _REFRESH_TIMESTAMP_KEYS:
            value = data.get(key)
            if isinstance(value, datetime):
                timestamps.append(value)

    assert timestamps, "expected visible graph nodes to expose a refresh timestamp"
    return max(timestamps)


def test_live_refresh_keeps_visible_state_fresh_within_500_ms() -> None:
    """Visible graph state should never drift more than 500 ms behind reality."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    command = StartSessionCommand(
        command_id="cmd-start-002",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="The hallway remembers every footstep."),
    )

    runtime.handle_command(command)
    sleep(0.55)

    latest_refresh_at = _latest_refresh_timestamp(runtime)
    age_ms = (datetime.now(timezone.utc) - latest_refresh_at).total_seconds() * 1000

    assert age_ms <= 500.0
