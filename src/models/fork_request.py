"""Fork request model representing user intent to branch from the active graph."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["ForkRequest", "ForkRequestStatus"]

_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class ForkRequestStatus(StrEnum):
    """Lifecycle states for a fork request."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class ForkRequest(StrictBaseModel):
    """Represents user intent to branch from the active graph's current node.

    Captures the source graph, selected node, user-provided seed, and confirmation
    state for the TUI fork flow.

    State transitions:
        - draft -> confirmed -> applied (when user confirms and fork succeeds)
        - draft -> cancelled (when user dismisses/cancels prompt)
    """

    active_graph_id: str = Field(
        min_length=1,
        description="Source graph used for forking (UUID)",
    )
    current_node_id: str = Field(
        min_length=1,
        description="Selected node to fork from",
    )
    seed: _SeedText | None = Field(
        default=None,
        description="User-provided seed; null means default seed behavior",
    )
    confirm: bool = Field(
        default=False,
        description="Whether user confirmed creation",
    )
    status: ForkRequestStatus = Field(
        default=ForkRequestStatus.DRAFT,
        description="Current state of the fork request",
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
