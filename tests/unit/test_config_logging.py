"""Tests for configuration logging helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import config
from config import logging_config


def test_setup_logging_applies_env_level_and_formatter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Logging setup should apply runtime level and formatter settings."""

    captured: dict[str, object] = {}
    original_level = logging_config.LOGGING_CONFIG["root"]["level"]
    original_console_level = logging_config.LOGGING_CONFIG["handlers"]["console"][
        "level"
    ]
    original_formatter = logging_config.LOGGING_CONFIG["handlers"]["console"][
        "formatter"
    ]

    monkeypatch.setattr(
        "config.env.get_settings",
        lambda: SimpleNamespace(log_level="debug", log_formatter="detailed"),
    )

    def _fake_dict_config(value: object) -> None:
        captured["config"] = value
        if isinstance(value, dict):
            captured["root_level"] = value["root"]["level"]
            captured["console_level"] = value["handlers"]["console"]["level"]
            captured["console_formatter"] = value["handlers"]["console"]["formatter"]

    monkeypatch.setattr("logging.config.dictConfig", _fake_dict_config)

    try:
        logging_config.setup_logging()
    finally:
        logging_config.LOGGING_CONFIG["root"]["level"] = original_level
        logging_config.LOGGING_CONFIG["handlers"]["console"]["level"] = (
            original_console_level
        )
        logging_config.LOGGING_CONFIG["handlers"]["console"]["formatter"] = (
            original_formatter
        )

    assert captured["config"] is logging_config.LOGGING_CONFIG
    assert captured["root_level"] == "DEBUG"
    assert captured["console_level"] == "DEBUG"
    assert captured["console_formatter"] == "detailed"


def test_config_setup_logging_delegates_to_logging_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public config wrapper should call logging_config.setup_logging."""

    calls: list[str] = []
    monkeypatch.setattr(
        "config.logging_config.setup_logging",
        lambda: calls.append("called"),
    )

    config.setup_logging()

    assert calls == ["called"]
