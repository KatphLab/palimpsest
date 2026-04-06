"""Tests for the command-line entry point."""

from types import SimpleNamespace

import pytest

import main as main_module


def test_main_uses_textual_mode_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The entry point should prefer Textual mode when no fallback is requested."""

    calls: list[str] = []
    runtime = SimpleNamespace()

    monkeypatch.setattr(main_module, "SessionRuntime", lambda: runtime)

    def fake_run_textual_mode(incoming_runtime: object) -> int:
        _ = incoming_runtime
        calls.append("textual")
        return 0

    def fake_run_cli_fallback(incoming_runtime: object) -> int:
        _ = incoming_runtime
        calls.append("cli")
        return 0

    monkeypatch.setattr(main_module, "run_textual_mode", fake_run_textual_mode)
    monkeypatch.setattr(main_module, "run_cli_fallback", fake_run_cli_fallback)

    exit_code = main_module.main([])

    assert exit_code == 0
    assert calls == ["textual"]


def test_main_uses_cli_fallback_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    """The entry point should expose a CLI fallback flag."""

    calls: list[str] = []
    runtime = SimpleNamespace()

    monkeypatch.setattr(main_module, "SessionRuntime", lambda: runtime)

    def fake_run_textual_mode(incoming_runtime: object) -> int:
        _ = incoming_runtime
        calls.append("textual")
        return 0

    def fake_run_cli_fallback(incoming_runtime: object) -> int:
        _ = incoming_runtime
        calls.append("cli")
        return 0

    monkeypatch.setattr(main_module, "run_textual_mode", fake_run_textual_mode)
    monkeypatch.setattr(main_module, "run_cli_fallback", fake_run_cli_fallback)

    exit_code = main_module.main(["--cli"])

    assert exit_code == 0
    assert calls == ["cli"]
