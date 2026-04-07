"""Textual application shell for the session runtime."""

from __future__ import annotations

from uuid import UUID

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Static

from models.commands import CommandResult
from models.common import SessionStatus
from runtime.session_runtime import SessionRuntime
from tui.screens import SeedEntryScreen, handle_pause_request, handle_resume_request
from tui.story_projection import build_story_lines
from tui.widgets import (
    SessionSwitcher,
    ShortcutFooterBar,
    build_entropy_hotspot_lines,
    build_mutation_log_lines,
    build_node_detail_lines,
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

    #active-session-scroll {
        height: 1fr;
    }

    #shortcut-footer {
        dock: bottom;
    }
    """

    BINDINGS = [
        ("s", "start_session", "Start"),
        ("p", "pause_session", "Pause"),
        ("r", "resume_session", "Resume"),
        ("c", "continue_session", "Continue"),
    ]

    def __init__(self, runtime: SessionRuntime | None = None) -> None:
        super().__init__()
        self.runtime = runtime or SessionRuntime()
        self.session_switcher = SessionSwitcher(runtime=self.runtime)
        self._is_generating_scene = False
        self._footer_bar = ShortcutFooterBar(id="shortcut-footer")

    def compose(self) -> ComposeResult:
        """Render the application shell."""

        yield Header()
        with Container(id="active-session"):
            with ScrollableContainer(id="active-session-scroll"):
                yield Static(self._render_session_panel(), id="active-session-panel")
        yield self._footer_bar

    def on_mount(self) -> None:
        """Initialize without automatic refresh polling."""

    def action_start_session(self) -> None:
        """Open the seed entry screen."""

        if self.runtime.session_id is not None:
            self.notify("A session is already running", severity="warning")
            return

        self.push_screen(
            SeedEntryScreen(self.runtime),
            callback=lambda _: self._refresh_active_session_panel(),
        )

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

    def action_continue_session(self) -> None:
        """Advance one manual cycle and refresh the active panel."""

        if self.runtime.session is None:
            self.notify("No active session", severity="warning")
            return

        if self._is_generating_scene:
            self.notify("Generation already in progress", severity="warning")
            return

        if self.runtime.session.status is not SessionStatus.RUNNING:
            self.notify("Session must be running", severity="warning")
            return

        self._set_generating_scene(True)
        self._start_continue_generation_worker()

    def _set_generating_scene(self, is_generating: bool) -> None:
        self._is_generating_scene = is_generating
        self._footer_bar.set_generating(is_generating)

    def _start_continue_generation_worker(self) -> None:
        self._run_continue_generation()

    @work(thread=True, exclusive=True)
    def _run_continue_generation(self) -> None:
        error_message: str | None = None
        try:
            self.runtime.advance_session_cycle()
        except Exception as error:  # pragma: no cover - defensive runtime boundary
            error_message = f"Generation failed: {error}"
        finally:
            self.call_from_thread(self._complete_continue_generation, error_message)

    def _complete_continue_generation(self, error_message: str | None) -> None:
        if error_message is not None:
            self.notify(error_message, severity="error")
        self._refresh_active_session_panel()
        self._set_generating_scene(False)

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

        if self.runtime.session is not None:
            lines.extend(
                build_story_lines(
                    session_graph=self.runtime.session_graph,
                    session=self.runtime.session,
                )
            )
            lines.extend(
                build_entropy_hotspot_lines(session_graph=self.runtime.session_graph)
            )
            lines.extend(
                build_node_detail_lines(
                    session_graph=self.runtime.session_graph,
                    session=self.runtime.session,
                )
            )
            lines.extend(
                build_mutation_log_lines(
                    event_log=getattr(self.runtime, "event_log", None)
                )
            )

        return "\n".join(lines)
