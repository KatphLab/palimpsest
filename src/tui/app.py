"""Textual application shell for the session runtime."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

from models.common import SessionStatus
from runtime.session_runtime import SessionRuntime
from tui.screens import SeedEntryScreen, handle_pause_request, handle_resume_request

__all__ = ["SessionApp"]


class SessionApp(App[None]):
    """Textual shell for observing and controlling a live session."""

    TITLE = "Palimpsest"
    CSS = """
    #active-session {
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("s", "start_session", "Start"),
        ("p", "pause_session", "Pause"),
        ("r", "resume_session", "Resume"),
    ]

    def __init__(self, runtime: SessionRuntime | None = None) -> None:
        super().__init__()
        self.runtime = runtime or SessionRuntime()

    def compose(self) -> ComposeResult:
        """Render the application shell."""

        yield Header()
        with Container(id="active-session"):
            yield Static(self._render_session_panel(), id="active-session-panel")
        yield Footer()

    def on_mount(self) -> None:
        """Start the refresh subscription."""

        self.set_interval(0.25, self._refresh_active_session_panel)

    def action_start_session(self) -> None:
        """Open the seed entry screen."""

        self.push_screen(SeedEntryScreen(self.runtime))

    def action_pause_session(self) -> None:
        """Pause the current runtime session."""

        if self.runtime.session_id is None:
            return

        handle_pause_request(self.runtime)

    def action_resume_session(self) -> None:
        """Resume the current runtime session."""

        if self.runtime.session_id is None:
            return

        handle_resume_request(self.runtime)

    def _refresh_active_session_panel(self) -> None:
        panel = self.query_one("#active-session-panel", Static)
        panel.update(self._render_session_panel())

    def _render_session_panel(self) -> str:
        if self.runtime.session_id is None:
            return "No active session. Press s to start one."

        status = (
            self.runtime.session.status
            if self.runtime.session
            else SessionStatus.CREATED
        )
        return (
            f"Session: {self.runtime.session_id}\n"
            f"Status: {status}\n"
            f"State version: {self.runtime.state_version}\n"
            f"Nodes: {self.runtime.session_graph.graph.number_of_nodes()}"
        )
