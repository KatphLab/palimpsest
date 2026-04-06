"""TUI screens and interaction handlers for session control."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from models.commands import (
    CommandResult,
    CommandType,
    EmptyPayload,
    PauseSessionCommand,
    ResumeSessionCommand,
    StartSessionCommand,
    StartSessionPayload,
)
from runtime.session_runtime import SessionRuntime

__all__ = [
    "SeedEntryScreen",
    "handle_pause_request",
    "handle_resume_request",
    "handle_seed_submission",
]


def handle_seed_submission(runtime: SessionRuntime, seed_text: str) -> CommandResult:
    """Submit a seed string to the runtime."""

    command = StartSessionCommand(
        command_id="ui-start-session",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text=seed_text),
    )
    return runtime.handle_command(command)


def handle_pause_request(runtime: SessionRuntime) -> CommandResult:
    """Pause the active session through the runtime."""

    command = PauseSessionCommand(
        command_id="ui-pause-session",
        command_type=CommandType.PAUSE_SESSION,
        payload=EmptyPayload(),
    )
    return runtime.handle_command(command)


def handle_resume_request(runtime: SessionRuntime) -> CommandResult:
    """Resume the active session through the runtime."""

    command = ResumeSessionCommand(
        command_id="ui-resume-session",
        command_type=CommandType.RESUME_SESSION,
        payload=EmptyPayload(),
    )
    return runtime.handle_command(command)


class SeedEntryScreen(Screen[CommandResult | None]):
    """Screen that collects seed text before starting a session."""

    BINDINGS = [("escape", "dismiss_screen", "Dismiss")]

    def __init__(self, runtime: SessionRuntime) -> None:
        super().__init__()
        self.runtime = runtime

    def compose(self) -> ComposeResult:
        """Render the seed entry form."""

        yield Static("Enter a seed to begin the session.")
        yield Input(placeholder="Seed text", id="seed-input")
        yield Button("Start session", id="start-session")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start a session when the button is pressed."""

        if event.button.id != "start-session":
            return

        seed_input = self.query_one(Input)
        result = handle_seed_submission(self.runtime, seed_input.value)
        self.dismiss(result)

    def action_dismiss_screen(self) -> None:
        """Close the screen without starting a session."""

        self.dismiss(None)
