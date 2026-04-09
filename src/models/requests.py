"""Request models for graph lifecycle operations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel
from utils.request_validators import (
    CUSTOM_SEED_MAX_LENGTH,
    CUSTOM_SEED_MIN_LENGTH,
    SeedText,
    validate_node_id,
    validate_seed_text,
)
from utils.uuid_validation import ensure_valid_uuid

__all__ = [
    "CUSTOM_SEED_MAX_LENGTH",
    "CUSTOM_SEED_MIN_LENGTH",
    "ForkFromCurrentNodeRequest",
    "GraphForkRequest",
    "GraphNavigationDirection",
    "GraphSwitchRequest",
]

_ForkEdgeId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_ForkLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class GraphForkRequest(StrictBaseModel):
    """Request payload to fork a source graph at a specific edge."""

    source_graph_id: str = Field(min_length=1)
    fork_edge_id: _ForkEdgeId
    custom_seed: SeedText | None = None
    label: _ForkLabel | None = None

    @field_validator("source_graph_id")
    @classmethod
    def _validate_source_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="source_graph_id")

    @field_validator("custom_seed")
    @classmethod
    def _validate_custom_seed_boundaries(cls, value: str | None) -> str | None:
        return validate_seed_text(value, field_name="custom_seed")


class ForkFromCurrentNodeRequest(StrictBaseModel):
    """Request to fork from the active graph's current node via TUI.

    Contract per CA-003: contains active graph identifier, current node
    identifier, and user-provided seed value.
    """

    active_graph_id: str = Field(
        min_length=1,
        description="Active graph identifier (UUID) used for forking",
    )
    current_node_id: str = Field(
        min_length=1,
        description="Current node identifier to fork from",
    )
    seed: SeedText | None = Field(
        default=None,
        description="User-provided seed value; null means default behavior",
    )

    @field_validator("active_graph_id")
    @classmethod
    def _validate_active_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="active_graph_id")

    @field_validator("current_node_id")
    @classmethod
    def _validate_current_node_id(cls, value: str) -> str:
        return validate_node_id(value, field_name="current_node_id")

    @field_validator("seed")
    @classmethod
    def _validate_seed(cls, value: str | None) -> str | None:
        return validate_seed_text(value, field_name="seed")


class GraphNavigationDirection(StrEnum):
    """Direction for graph switching navigation."""

    NEXT = "next"  # Corresponds to Tab key
    PREVIOUS = "previous"  # Corresponds to Shift+Tab key


class GraphSwitchRequest(StrictBaseModel):
    """Request payload to activate a graph in the multi-graph view.

    Contract per CA-003: contains target graph identifier and navigation
    direction (next or previous).
    """

    target_graph_id: str = Field(min_length=1)
    preserve_current: bool = True
    direction: GraphNavigationDirection | None = Field(
        default=None,
        description="Navigation direction used to select the target graph",
    )

    @field_validator("target_graph_id")
    @classmethod
    def _validate_target_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="target_graph_id")
