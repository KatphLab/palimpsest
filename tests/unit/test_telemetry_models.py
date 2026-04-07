"""Tests for telemetry model exports and strictness."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from importlib.util import find_spec
from types import ModuleType

import pytest
from pydantic import ValidationError

import models


def _telemetry_module() -> ModuleType:
    from importlib import import_module

    return import_module("models.telemetry")


def test_models_telemetry_module_exists() -> None:
    """The telemetry module should be importable from the models package."""

    assert find_spec("models.telemetry") is not None


def test_models_telemetry_reexports_common_models() -> None:
    """Telemetry exports should reuse the shared common model classes."""

    telemetry = _telemetry_module()

    assert telemetry.BudgetTelemetry is models.BudgetTelemetry
    assert telemetry.CoherenceSnapshot is models.CoherenceSnapshot
    assert telemetry.NodeCoherenceScore is models.NodeCoherenceScore


def test_models_telemetry_rejects_extra_fields() -> None:
    """Telemetry models must remain strict about undeclared fields."""

    telemetry = _telemetry_module()
    sampled_at = datetime(2026, 4, 7, tzinfo=timezone.utc)

    with pytest.raises(ValidationError):
        telemetry.BudgetTelemetry(
            estimated_cost_usd=Decimal("0.00"),
            budget_limit_usd=Decimal("5.00"),
            token_input_count=0,
            token_output_count=0,
            model_call_count=0,
            unexpected_field=True,
        )

    with pytest.raises(ValidationError):
        telemetry.CoherenceSnapshot(
            global_score=1.0,
            local_scores=[],
            global_check_status=telemetry.CheckStatus.PASS,
            sampled_at=sampled_at,
            checked_by="test",
            unexpected_field=True,
        )
