"""Textual application shell for the session runtime."""

from __future__ import annotations

from uuid import UUID

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

from models.commands import CommandResult
from models.common import NodeKind, SessionStatus
from runtime.session_runtime import SessionRuntime
from tui.screens import SeedEntryScreen, handle_pause_request, handle_resume_request
from tui.widgets import (
    SessionSwitcher,
    handle_fork_request,
    handle_lock_request,
    handle_unlock_request,
)

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
        self.session_switcher = SessionSwitcher(runtime=self.runtime)

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

        if self.runtime.session_id is not None:
            self.notify("A session is already running", severity="warning")
            return

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

        result = handle_resume_request(self.runtime)
        if not result.accepted:
            self.notify(result.message, severity="warning")

    def switch_session(self, session_id: UUID) -> None:
        """Switch the active runtime session through the wrapper."""

        self.session_switcher.switch_session(session_id)

    def lock_edge(self, edge_id: str) -> CommandResult:
        """Lock a graph edge through the runtime command router."""

        return handle_lock_request(self.runtime, edge_id)

    def unlock_edge(self, edge_id: str) -> CommandResult:
        """Unlock a graph edge through the runtime command router."""

        return handle_unlock_request(self.runtime, edge_id)

    def fork_session(self, fork_label: str | None = None) -> CommandResult:
        """Fork the active session through the runtime command router."""

        return handle_fork_request(self.runtime, fork_label=fork_label)

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

        # Build the base session info
        lines = [
            f"Session: {self.runtime.session_id}",
            f"Status: {status}",
            f"State version: {self.runtime.state_version}",
            f"Nodes: {self.runtime.session_graph.graph.number_of_nodes()}",
            "",
        ]

        # Show the seed text
        if self.runtime.session and self.runtime.session.seed_text:
            lines.append("─" * 40)
            lines.append("🌱 SEED")
            lines.append(self.runtime.session.seed_text)
            lines.append("")

        # Show generated scenes from the graph nodes
        for node_id, node_data in self.runtime.session_graph.graph.nodes(data=True):
            graph_node = node_data.get("node")
            if graph_node and graph_node.node_kind == NodeKind.SCENE:
                lines.append("─" * 40)
                lines.append("🎭 SCENE")
                lines.append(graph_node.text)
                lines.append("")

        return "\n".join(lines)
