"""Structured logging helpers for graph operation telemetry."""

from __future__ import annotations

import json
import logging

from pydantic import Field, JsonValue, field_validator, model_validator

from models.common import StrictBaseModel, UTCDateTime
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["OperationLogEntry", "log_operation"]


class OperationLogEntry(StrictBaseModel):
    """Structured payload for fork/create/switch/delete operation logs."""

    operation: str = Field(min_length=1)
    status: str = Field(min_length=1)
    graph_id: str | None = None
    started_at: UTCDateTime
    completed_at: UTCDateTime | None = None
    duration_ms: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("graph_id")
    @classmethod
    def _validate_graph_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return ensure_valid_uuid(value, field_name="graph_id")

    @model_validator(mode="after")
    def _set_duration(self) -> OperationLogEntry:
        if self.completed_at is None:
            return self

        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be on or after started_at")

        if self.duration_ms is None:
            delta = self.completed_at - self.started_at
            self.duration_ms = round(delta.total_seconds() * 1000, 3)

        return self

    def to_payload(self) -> dict[str, JsonValue]:
        """Build a JSON-serializable payload with normalized timestamps."""

        payload: dict[str, JsonValue] = {
            "operation": self.operation,
            "status": self.status,
            "started_at": _format_timestamp(self.started_at),
            "metadata": self.metadata,
        }
        if self.graph_id is not None:
            payload["graph_id"] = self.graph_id
        if self.completed_at is not None:
            payload["completed_at"] = _format_timestamp(self.completed_at)
        if self.duration_ms is not None:
            payload["duration_ms"] = self.duration_ms

        return payload


def log_operation(
    logger: logging.Logger,
    entry: OperationLogEntry,
    *,
    level: int = logging.INFO,
) -> None:
    """Emit an operation log line as a single JSON object."""

    logger.log(level, json.dumps(entry.to_payload(), sort_keys=True))


def _format_timestamp(timestamp: UTCDateTime) -> str:
    """Render UTC timestamp as an ISO-8601 string with ``Z`` suffix."""

    return timestamp.isoformat().replace("+00:00", "Z")
