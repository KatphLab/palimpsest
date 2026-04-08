"""Tests for UUID validation helpers used by graph models."""

from __future__ import annotations

import pytest

from utils.uuid_validation import ensure_valid_uuid, is_valid_uuid


def test_is_valid_uuid_accepts_contract_compliant_value() -> None:
    """Validation helper should accept lowercase canonical UUID strings."""

    assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True


def test_is_valid_uuid_rejects_uppercase_values() -> None:
    """Validation helper should enforce the contract's lowercase UUID pattern."""

    assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000") is False


def test_ensure_valid_uuid_raises_for_invalid_input() -> None:
    """Strict validation helper should raise with field context."""

    with pytest.raises(ValueError, match="source_graph_id"):
        ensure_valid_uuid("not-a-uuid", field_name="source_graph_id")
