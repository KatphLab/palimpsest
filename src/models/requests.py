"""Request models for graph lifecycle operations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel
from utils.uuid_validation import ensure_valid_uuid

__all__ = [
    "CUSTOM_SEED_MAX_LENGTH",
    "CUSTOM_SEED_MIN_LENGTH",
    "ForkFromCurrentNodeRequest",
    "GraphForkRequest",
    "GraphNavigationDirection",
    "GraphSwitchRequest",
]

CUSTOM_SEED_MIN_LENGTH = 1
CUSTOM_SEED_MAX_LENGTH = 255

_ForkEdgeId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
_SeedText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=CUSTOM_SEED_MIN_LENGTH,
        max_length=CUSTOM_SEED_MAX_LENGTH,
    ),
]
_ForkLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class GraphForkRequest(StrictBaseModel):
    """Request payload to fork a source graph at a specific edge."""

    source_graph_id: str = Field(min_length=1)
    fork_edge_id: _ForkEdgeId
    custom_seed: _SeedText | None = None
    label: _ForkLabel | None = None

    @field_validator("source_graph_id")
    @classmethod
    def _validate_source_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="source_graph_id")

    @field_validator("custom_seed")
    @classmethod
    def _validate_custom_seed_boundaries(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if len(value) < CUSTOM_SEED_MIN_LENGTH or len(value) > CUSTOM_SEED_MAX_LENGTH:
            raise ValueError(
                "custom_seed must be between "
                f"{CUSTOM_SEED_MIN_LENGTH} and {CUSTOM_SEED_MAX_LENGTH} characters"
            )

        return value


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
    seed: _SeedText | None = Field(
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
        if len(value.strip()) < 1:
            raise ValueError("current_node_id must be non-empty")

        return value

    @field_validator("seed")
    @classmethod
    def _validate_seed(cls, value: str | None) -> str | None:
        if value is None:
            return None

        stripped = value.strip()
        if len(stripped) < 1:
            raise ValueError("seed must be at least 1 character when provided")

        if len(stripped) > 255:
            raise ValueError("seed must not exceed 255 characters")

        return stripped


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
