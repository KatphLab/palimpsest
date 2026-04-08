"""Request models for graph lifecycle operations."""

from __future__ import annotations

from pydantic import ConfigDict, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel
from utils.uuid_validation import ensure_valid_uuid

__all__ = [
    "CUSTOM_SEED_MAX_LENGTH",
    "CUSTOM_SEED_MIN_LENGTH",
    "GraphForkRequest",
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

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_graph_id: str = Field(min_length=1, alias="sourceGraphId")
    fork_edge_id: _ForkEdgeId = Field(alias="forkEdgeId")
    custom_seed: _SeedText | None = Field(default=None, alias="customSeed")
    label: _ForkLabel | None = Field(default=None, alias="label")

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


class GraphSwitchRequest(StrictBaseModel):
    """Request payload to activate a graph in the multi-graph view."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target_graph_id: str = Field(min_length=1, alias="targetGraphId")
    preserve_current: bool = Field(default=True, alias="preserveCurrent")

    @field_validator("target_graph_id")
    @classmethod
    def _validate_target_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="target_graph_id")
