"""Unit tests for TUI screen handlers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from models.commands import (
    CommandResult,
    CommandType,
    PauseSessionCommand,
    ResumeSessionCommand,
    StartSessionCommand,
)
from runtime.session_runtime import SessionRuntime
from tui.screens import (
    SeedEntryScreen,
    handle_pause_request,
    handle_resume_request,
    handle_seed_submission,
)


class _RuntimeStub:
    def __init__(self) -> None:
        self.commands: list[object] = []

    def handle_command(self, command: object) -> CommandResult:
        self.commands.append(command)
        return CommandResult(
            command_id="result-1",
            accepted=True,
            message="ok",
            state_version=1,
        )


def test_screen_command_handlers_build_expected_command_types() -> None:
    """Screen command helpers should route typed command envelopes."""

    runtime = _RuntimeStub()

    runtime_for_handler = cast(SessionRuntime, runtime)
    _ = handle_seed_submission(runtime_for_handler, "seed text")
    _ = handle_pause_request(runtime_for_handler)
    _ = handle_resume_request(runtime_for_handler)

    assert isinstance(runtime.commands[0], StartSessionCommand)
    assert runtime.commands[0].command_type is CommandType.START_SESSION
    assert runtime.commands[0].payload.seed_text == "seed text"
    assert isinstance(runtime.commands[1], PauseSessionCommand)
    assert runtime.commands[1].command_type is CommandType.PAUSE_SESSION
    assert isinstance(runtime.commands[2], ResumeSessionCommand)
    assert runtime.commands[2].command_type is CommandType.RESUME_SESSION


def test_seed_entry_screen_button_paths_and_dismiss_action() -> None:
    """Screen should ignore unrelated buttons and submit start requests."""

    runtime = _RuntimeStub()
    screen = SeedEntryScreen(cast(SessionRuntime, runtime))
    dismissed: list[object | None] = []

    cast(Any, screen).query_one = lambda *_: SimpleNamespace(value="from input")
    cast(Any, screen).dismiss = lambda result: dismissed.append(result)

    _ = list(screen.compose())

    screen.on_button_pressed(
        cast(Any, SimpleNamespace(button=SimpleNamespace(id="other-button")))
    )
    screen.on_button_pressed(
        cast(Any, SimpleNamespace(button=SimpleNamespace(id="start-session")))
    )
    screen.action_dismiss_screen()

    assert len(runtime.commands) == 1
    assert isinstance(runtime.commands[0], StartSessionCommand)
    assert dismissed[0] is not None
    assert dismissed[1] is None
