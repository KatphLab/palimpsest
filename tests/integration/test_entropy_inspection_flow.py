"""Integration tests for entropy-aware node inspection."""

from __future__ import annotations

import pytest

from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import (
    CommandType,
    InspectNodeCommand,
    InspectNodePayload,
    StartSessionCommand,
    StartSessionPayload,
)
from models.node import SceneNode
from runtime.session_runtime import SessionRuntime
from tests.fixtures import DeterministicSceneGenerationProvider

pytestmark = pytest.mark.integration


def test_inspect_node_surfaces_entropy_drift_and_chronology() -> None:
    """Node inspection should expose entropy, drift, and chronology context."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
    )
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-entropy-inspection-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(
                seed_text="A lantern flickers while the hallway listens."
            ),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    assert runtime.session.active_node_ids

    inspected_node_id = runtime.session.active_node_ids[-1]
    scene_node = SceneNode.model_validate(
        runtime.session_graph.graph.nodes[inspected_node_id]["scene_node"].model_dump()
    )

    inspect_result = runtime.handle_command(
        InspectNodeCommand(
            command_id="cmd-inspect-entropy-001",
            command_type=CommandType.INSPECT_NODE,
            session_id=start_result.session_id,
            payload=InspectNodePayload(node_id=inspected_node_id),
        )
    )

    assert inspect_result.accepted is True
    assert inspect_result.session_id == start_result.session_id
    assert inspected_node_id in inspect_result.message
    assert "entropy" in inspect_result.message
    assert f"{scene_node.entropy_score:.2f}" in inspect_result.message
    assert scene_node.drift_category is not None
    assert scene_node.drift_category.value in inspect_result.message
    assert "chronology" in inspect_result.message
    assert start_result.message in inspect_result.message
