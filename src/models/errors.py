"""Error models and codes for graph forking operations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, JsonValue

from models.common import StrictBaseModel

__all__ = ["ERROR_STATUS_CODES", "ForkErrorCode", "GraphForkError"]


class ForkErrorCode(StrEnum):
    """Enumerated error codes for graph forking outcomes."""

    SOURCE_GRAPH_NOT_FOUND = "SOURCE_GRAPH_NOT_FOUND"
    EDGE_NOT_FOUND = "EDGE_NOT_FOUND"
    INVALID_SEED = "INVALID_SEED"
    GRAPH_LIMIT_EXCEEDED = "GRAPH_LIMIT_EXCEEDED"
    FORK_CYCLE_DETECTED = "FORK_CYCLE_DETECTED"
    COHERENCE_VIOLATION = "COHERENCE_VIOLATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class GraphForkError(StrictBaseModel):
    """Typed error payload returned for failed fork operations."""

    error: ForkErrorCode
    message: str = Field(min_length=1)
    details: dict[str, JsonValue] | None = None


ERROR_STATUS_CODES: dict[ForkErrorCode, int] = {
    ForkErrorCode.SOURCE_GRAPH_NOT_FOUND: 404,
    ForkErrorCode.EDGE_NOT_FOUND: 404,
    ForkErrorCode.INVALID_SEED: 400,
    ForkErrorCode.GRAPH_LIMIT_EXCEEDED: 429,
    ForkErrorCode.FORK_CYCLE_DETECTED: 400,
    ForkErrorCode.COHERENCE_VIOLATION: 422,
    ForkErrorCode.INTERNAL_ERROR: 500,
}
