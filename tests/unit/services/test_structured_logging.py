"""Tests for structured operation logging utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from services.structured_logging import OperationLogEntry, log_operation


def test_log_operation_emits_json_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Operation logger should emit machine-readable JSON payloads."""

    logger = logging.getLogger("tests.structured")
    started_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(milliseconds=130)
    entry = OperationLogEntry(
        operation="fork",
        status="success",
        graph_id="550e8400-e29b-41d4-a716-446655440000",
        started_at=started_at,
        completed_at=completed_at,
        metadata={"source_graph_id": "550e8400-e29b-41d4-a716-446655440001"},
    )

    caplog.set_level(logging.INFO, logger="tests.structured")
    log_operation(logger, entry)

    payload = json.loads(caplog.records[0].message)
    assert payload["operation"] == "fork"
    assert payload["status"] == "success"
    assert payload["graph_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["duration_ms"] == 130.0
    assert payload["started_at"] == "2026-04-08T10:00:00Z"


def test_operation_log_entry_infers_duration() -> None:
    """Entries with start/end timestamps should auto-populate durations."""

    started_at = datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(milliseconds=25)

    entry = OperationLogEntry(
        operation="switch",
        status="success",
        started_at=started_at,
        completed_at=completed_at,
    )

    assert entry.duration_ms == 25.0
