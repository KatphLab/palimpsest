"""Models for multi-graph list and browsing views."""

from __future__ import annotations

from pydantic import ConfigDict, Field, StringConstraints, field_validator
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

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    name: _GraphName
    node_count: int = Field(ge=0, alias="nodeCount")
    edge_count: int = Field(ge=0, alias="edgeCount")
    created_at: UTCDateTime = Field(alias="createdAt")
    fork_source: str | None = Field(default=None, alias="forkSource")
    current_state: _CurrentState = Field(alias="currentState")
    last_modified: UTCDateTime = Field(alias="lastModified")
    seed: _SeedText | None = Field(default=None, alias="seed")
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
