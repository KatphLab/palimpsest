"""Models for multi-graph list and browsing views."""

from __future__ import annotations

from pydantic import Field, StringConstraints, field_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel, UTCDateTime
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["GraphSummary"]

_GraphName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
_CurrentState = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class GraphSummary(StrictBaseModel):
    """Lightweight metadata representation for a graph instance."""

    id: str = Field(min_length=1)
    name: _GraphName
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    created_at: UTCDateTime
    fork_source: str | None = None
    current_state: _CurrentState
    last_modified: UTCDateTime
    seed: _SeedText | None = None
    labels: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="id")

    @field_validator("fork_source")
    @classmethod
    def _validate_fork_source(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return ensure_valid_uuid(value, field_name="fork_source")
