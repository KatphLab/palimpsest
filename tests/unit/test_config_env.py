"""Tests for environment-backed runtime settings."""

from __future__ import annotations

from decimal import Decimal

from pydantic import SecretStr

from config.env import Settings


def test_settings_use_production_defaults_for_runtime_limits() -> None:
    """Settings should expose expected production-safe default limits."""

    settings = Settings(openai_api_key=SecretStr("test-key"))

    assert settings.stale_view_guardrail_ms == 500
    assert settings.global_consistency_check_interval_ms == 60_000
    assert settings.session_mutation_cooldown_ms == 30_000
    assert settings.session_coherence_target == 0.80
    assert settings.session_budget_usd == Decimal("5.00")


def test_settings_runtime_limit_fields_include_descriptions() -> None:
    """Runtime limit fields should include human-readable metadata."""

    model_fields = Settings.model_fields

    assert (
        model_fields["stale_view_guardrail_ms"].description
        == "Maximum age in milliseconds before the active view is considered stale."
    )
    assert (
        model_fields["global_consistency_check_interval_ms"].description
        == "Interval in milliseconds between scheduled global consistency checks."
    )
    assert (
        model_fields["session_mutation_cooldown_ms"].description
        == "Cooldown period in milliseconds before another mutation can be applied."
    )
    assert (
        model_fields["session_coherence_target"].description
        == "Target minimum global coherence score for a running session."
    )
    assert (
        model_fields["session_budget_usd"].description
        == "Maximum expected session spend in USD before budget alerts are emitted."
    )
