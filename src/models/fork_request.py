"""Fork request model representing user intent to branch from the active graph."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from models.common import StrictBaseModel
from utils.request_validators import SeedText, validate_node_id, validate_seed_text
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["ForkRequest", "ForkRequestStatus"]


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
    seed: SeedText | None = Field(
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
        return validate_node_id(value, field_name="current_node_id")

    @field_validator("seed")
    @classmethod
    def _validate_seed(cls, value: str | None) -> str | None:
        return validate_seed_text(value, field_name="seed")
