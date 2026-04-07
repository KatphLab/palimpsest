"""Strict narrative context schemas for LLM mutation selection."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from models.common import MutationActionType, StrictBaseModel

__all__ = [
    "MutationActionSelection",
    "NarrativeContext",
    "NarrativeGraphCounters",
    "NarrativeSceneContext",
]

_NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class NarrativeSceneContext(StrictBaseModel):
    """Minimal scene snapshot used for the last-two-scenes narrative window."""

    scene_node_id: _NonEmptyText
    scene_text: _NonEmptyText


class NarrativeGraphCounters(StrictBaseModel):
    """Graph counters required for mutation selection context."""

    graph_version: int = Field(ge=0)
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    active_node_count: int = Field(ge=0)


class NarrativeContext(StrictBaseModel):
    """Narrative state snapshot for LLM mutation proposal selection."""

    session_id: UUID
    seed_node_id: _NonEmptyText
    previous_scene_node_id: _NonEmptyText
    current_scene_node_id: _NonEmptyText
    last_two_scenes: list[NarrativeSceneContext] = Field(min_length=2, max_length=2)
    graph_counters: NarrativeGraphCounters

    @model_validator(mode="after")
    def _validate_last_two_scenes(self) -> NarrativeContext:
        previous_scene, current_scene = self.last_two_scenes
        if previous_scene.scene_node_id != self.previous_scene_node_id:
            raise ValueError(
                "previous_scene_node_id must match the first last_two_scenes entry"
            )

        if current_scene.scene_node_id != self.current_scene_node_id:
            raise ValueError(
                "current_scene_node_id must match the second last_two_scenes entry"
            )

        return self


class MutationActionSelection(StrictBaseModel):
    """LLM-authored action selection for the mutation proposer/runtime."""

    source: Literal["llm"]
    action_type: MutationActionType
    target_ids: list[_NonEmptyText]
