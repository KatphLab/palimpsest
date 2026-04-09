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
from models.fork_request import ForkRequest
from runtime.session_runtime import SessionRuntime

__all__ = [
    "SeedEntryScreen",
    "ForkSeedEntryScreen",
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


class ForkSeedEntryScreen(Screen[ForkRequest | None]):
    """Screen that collects seed text for forking from the current node.

    Returns a ForkRequest when confirmed, or None when cancelled.
    """

    BINDINGS = [
        ("escape", "dismiss_screen", "Cancel"),
        ("enter", "confirm_fork", "Confirm"),
    ]

    def __init__(
        self,
        runtime: SessionRuntime,
        active_graph_id: str,
        current_node_id: str,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.active_graph_id = active_graph_id
        self.current_node_id = current_node_id

    def compose(self) -> ComposeResult:
        """Render the fork seed entry form."""

        yield Static(
            f"Fork from node '{self.current_node_id}'\n"
            "Enter a seed for the new graph (optional):"
        )
        yield Input(placeholder="Seed text (optional)", id="fork-seed-input")
        with Static(classes="button-row"):
            yield Button("Confirm Fork", id="confirm-fork", variant="primary")
            yield Button("Cancel", id="cancel-fork", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle fork confirmation or cancellation."""

        if event.button.id == "confirm-fork":
            self._confirm_fork()
        elif event.button.id == "cancel-fork":
            self._cancel_fork()

    def action_dismiss_screen(self) -> None:
        """Close the screen without forking (escape key)."""

        self._cancel_fork()

    def action_confirm_fork(self) -> None:
        """Confirm the fork (enter key)."""

        self._confirm_fork()

    def _confirm_fork(self) -> None:
        """Create fork request and dismiss with confirmed status."""

        seed_input = self.query_one("#fork-seed-input", Input)
        seed_text = seed_input.value.strip()

        # If empty seed, treat as None (default behavior)
        seed = seed_text if seed_text else None

        from models.fork_request import ForkRequestStatus

        fork_request = ForkRequest(
            active_graph_id=self.active_graph_id,
            current_node_id=self.current_node_id,
            seed=seed,
            confirm=True,
            status=ForkRequestStatus.CONFIRMED,
        )
        self.dismiss(fork_request)

    def _cancel_fork(self) -> None:
        """Cancel the fork and dismiss with None."""

        self.dismiss(None)
