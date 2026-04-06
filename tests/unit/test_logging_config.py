"""Tests for logging configuration wiring."""

from importlib import import_module

import pytest


def test_logging_config_uses_canonical_env_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Logging config should bind settings from the project package path."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    logging_config = import_module("config.logging_config")

    assert logging_config.get_settings.__module__ == "config.env"
