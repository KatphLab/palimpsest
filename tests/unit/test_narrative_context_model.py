"""Tests for strict narrative context schemas used by mutation selection."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from models.common import MutationActionType


def test_narrative_context_module_exports_public_api() -> None:
    """The narrative context module should publish its typed API."""

    from models import narrative_context

    assert narrative_context.__all__ == [
        "MutationActionSelection",
        "NarrativeContext",
        "NarrativeGraphCounters",
        "NarrativeSceneContext",
    ]


def test_narrative_context_forbids_extra_fields() -> None:
    """Narrative context models must reject undeclared fields."""

    from models.narrative_context import (
        NarrativeContext,
        NarrativeGraphCounters,
        NarrativeSceneContext,
    )

    with pytest.raises(ValidationError):
        NarrativeContext.model_validate(
            {
                "session_id": UUID("11111111-1111-1111-1111-111111111111"),
                "seed_node_id": "seed-1",
                "previous_scene_node_id": "scene-1",
                "current_scene_node_id": "scene-2",
                "last_two_scenes": [
                    {
                        "scene_node_id": "scene-1",
                        "scene_text": "The lantern flickers.",
                    },
                    {
                        "scene_node_id": "scene-2",
                        "scene_text": "The door opens.",
                    },
                ],
                "graph_counters": {
                    "graph_version": 7,
                    "node_count": 12,
                    "edge_count": 18,
                    "active_node_count": 2,
                },
                "unexpected": "value",
            }
        )

    context = NarrativeContext.model_validate(
        {
            "session_id": UUID("11111111-1111-1111-1111-111111111111"),
            "seed_node_id": "seed-1",
            "previous_scene_node_id": "scene-1",
            "current_scene_node_id": "scene-2",
            "last_two_scenes": [
                {
                    "scene_node_id": "scene-1",
                    "scene_text": "The lantern flickers.",
                },
                {
                    "scene_node_id": "scene-2",
                    "scene_text": "The door opens.",
                },
            ],
            "graph_counters": {
                "graph_version": 7,
                "node_count": 12,
                "edge_count": 18,
                "active_node_count": 2,
            },
        }
    )

    assert context.session_id == UUID("11111111-1111-1111-1111-111111111111")
    assert context.last_two_scenes == [
        NarrativeSceneContext(
            scene_node_id="scene-1",
            scene_text="The lantern flickers.",
        ),
        NarrativeSceneContext(
            scene_node_id="scene-2",
            scene_text="The door opens.",
        ),
    ]
    assert context.graph_counters == NarrativeGraphCounters(
        graph_version=7,
        node_count=12,
        edge_count=18,
        active_node_count=2,
    )


def test_mutation_action_selection_requires_llm_source() -> None:
    """Mutation action selection must be sourced from the LLM only."""

    from models.narrative_context import MutationActionSelection

    selection = MutationActionSelection.model_validate(
        {
            "source": "llm",
            "action_type": MutationActionType.REMOVE_EDGE,
            "target_ids": ["edge-1"],
        }
    )

    assert selection.source == "llm"
    assert selection.action_type is MutationActionType.REMOVE_EDGE

    with pytest.raises(ValidationError):
        MutationActionSelection.model_validate(
            {
                "source": "fallback",
                "action_type": MutationActionType.REMOVE_EDGE,
                "target_ids": ["edge-1"],
            }
        )
