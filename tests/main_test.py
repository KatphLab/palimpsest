"""Tests for the command-line entry point."""

from types import SimpleNamespace
from typing import cast

import pytest

import main as main_module
from runtime.session_runtime import SessionRuntime


def test_main_uses_textual_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The entry point should launch the TUI application."""

    calls: list[str] = []
    runtime = SimpleNamespace()
    monkeypatch.setattr(main_module, "SessionRuntime", lambda: runtime)
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)

    def fake_run_textual_mode(incoming_runtime: object) -> int:
        _ = incoming_runtime
        calls.append("textual")
        return 0

    monkeypatch.setattr(main_module, "run_textual_mode", fake_run_textual_mode)

    exit_code = main_module.main([])

    assert exit_code == 0
    assert calls == ["textual"]


def test_main_initializes_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """The entry point should initialize logging before launching TUI."""

    calls: list[str] = []
    runtime = SimpleNamespace()

    def mock_setup_logging() -> None:
        calls.append("setup_logging")

    monkeypatch.setattr(main_module, "SessionRuntime", lambda: runtime)
    monkeypatch.setattr(main_module, "setup_logging", mock_setup_logging)

    def fake_run_textual_mode(incoming_runtime: object) -> int:
        _ = incoming_runtime
        calls.append("textual")
        return 0

    monkeypatch.setattr(main_module, "run_textual_mode", fake_run_textual_mode)

    exit_code = main_module.main([])

    assert exit_code == 0
    assert "setup_logging" in calls
    assert "textual" in calls


def test_run_textual_mode_runs_session_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Textual mode should construct and run the SessionApp wrapper."""

    calls: list[str] = []
    runtime = SimpleNamespace()

    class _SessionAppStub:
        def __init__(self, runtime: object) -> None:
            _ = runtime
            calls.append("init")

        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(main_module, "SessionApp", _SessionAppStub)
    monkeypatch.setattr(main_module.LOGGER, "info", lambda *_: calls.append("log"))

    result = main_module.run_textual_mode(cast(SessionRuntime, runtime))

    assert result == 0
    assert calls == ["log", "init", "run"]
