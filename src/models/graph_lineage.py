"""Fork lineage model for parent-child graph ancestry."""

from __future__ import annotations

from pydantic import Field, StringConstraints, field_validator, model_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["GraphLineage"]

_BranchId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class GraphLineage(StrictBaseModel):
    """Parent-child relationship entry inside the fork tree."""

    parent_graph_id: str = Field(min_length=1)
    child_graph_id: str = Field(min_length=1)
    depth: int = Field(ge=0)
    branch_id: _BranchId

    @field_validator("parent_graph_id")
    @classmethod
    def _validate_parent_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="parent_graph_id")

    @field_validator("child_graph_id")
    @classmethod
    def _validate_child_graph_id(cls, value: str) -> str:
        return ensure_valid_uuid(value, field_name="child_graph_id")

    @model_validator(mode="after")
    def _validate_non_self_reference(self) -> GraphLineage:
        if self.parent_graph_id == self.child_graph_id:
            raise ValueError("parent_graph_id and child_graph_id must differ")

        return self
