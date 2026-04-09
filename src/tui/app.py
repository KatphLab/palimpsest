"""Textual application shell for the session runtime."""

from __future__ import annotations

from uuid import UUID

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Static

from models.commands import CommandResult
from models.common import SessionStatus
from models.fork_request import ForkRequest
from runtime.session_runtime import SessionRuntime
from tui.screens import (
    ForkSeedEntryScreen,
    SeedEntryScreen,
    handle_pause_request,
    handle_resume_request,
)
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
        padding: 0;
        height: 1fr;
    }

    #scene-text-scroll {
        height: 7fr;
        border-bottom: solid $surface-darken-1;
    }

    #telemetry-scroll {
        height: 3fr;
    }

    #scene-text-panel, #telemetry-panel {
        padding: 1 2;
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
        ("f", "fork_from_current_node", "Fork"),
    ]

    def __init__(self, runtime: SessionRuntime | None = None) -> None:
        super().__init__()
        self.runtime = runtime or SessionRuntime()
        self.session_switcher = SessionSwitcher(runtime=self.runtime)
        self._is_generating_scene = False
        self._footer_bar = ShortcutFooterBar(id="shortcut-footer")

    def compose(self) -> ComposeResult:
        """Render the application shell with split panels."""

        yield Header()
        with Container(id="active-session"):
            with ScrollableContainer(id="scene-text-scroll"):
                yield Static(self._render_scene_text(), id="scene-text-panel")
            with ScrollableContainer(id="telemetry-scroll"):
                yield Static(self._render_telemetry(), id="telemetry-panel")
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
            callback=lambda _: self._refresh_panels(),
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

    def action_fork_from_current_node(self) -> None:
        """Initiate fork flow from the current node when 'f' is pressed."""

        # Check if there's an active session (use getattr for compatibility with stubs)
        runtime_session = getattr(self.runtime, "session", None)
        if runtime_session is None:
            self.notify("No active session. Start a session first.", severity="warning")
            return

        # Create fork request from current context
        fork_request = self.runtime.create_fork_request(seed=None)

        if fork_request is None:
            self.notify(
                "No current node selected. Navigate to a node before forking.",
                severity="warning",
            )
            return

        # Push the fork seed entry screen
        self.push_screen(
            ForkSeedEntryScreen(
                self.runtime,
                active_graph_id=fork_request.active_graph_id,
                current_node_id=fork_request.current_node_id,
            ),
            callback=self._handle_fork_result,
        )

    def _handle_fork_result(self, fork_request: "ForkRequest | None") -> None:
        """Handle the result from the fork seed entry screen."""

        if fork_request is None:
            # User cancelled - T022
            self.notify("Fork cancelled", severity="information")
            return

        # User confirmed - T021
        # Convert ForkRequest to ForkFromCurrentNodeRequest for runtime
        from models.requests import ForkFromCurrentNodeRequest

        fork_from_request = ForkFromCurrentNodeRequest(
            active_graph_id=fork_request.active_graph_id,
            current_node_id=fork_request.current_node_id,
            seed=fork_request.seed,
        )

        try:
            new_session = self.runtime.fork_from_current_node(fork_from_request)
            if new_session is not None:
                self.notify(
                    f"Fork created: new graph is now active (total graphs: {self.runtime.graph_count})",
                    severity="information",
                )
                self._refresh_panels()
            else:
                self.notify("Failed to create fork", severity="error")
        except Exception as error:
            self.notify(f"Fork failed: {error}", severity="error")

    def action_cancel_fork(self) -> None:
        """Cancel the fork flow and return to normal operation."""

        # Attempt to pop screen - will fail gracefully if no screens to pop
        try:
            self.pop_screen()
        except Exception:
            # No screen to pop or not in screen context - safe to ignore
            pass
        self.notify("Fork cancelled", severity="information")

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
        self._refresh_panels()
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

    def _refresh_panels(self) -> None:
        """Refresh both scene text and telemetry panels."""

        try:
            scene_panel = self.query_one("#scene-text-panel", Static)
            scene_panel.update(self._render_scene_text())
        except Exception:
            pass  # Panel not yet mounted

        try:
            telemetry_panel = self.query_one("#telemetry-panel", Static)
            telemetry_panel.update(self._render_telemetry())
        except Exception:
            pass  # Panel not yet mounted

    def _render_scene_text(self) -> str:
        """Render scene text content (story flow)."""

        if self.runtime.session_id is None:
            return "No active session. Press s to start one."

        status = (
            self.runtime.session.status
            if self.runtime.session
            else SessionStatus.CREATED
        )

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

        return "\n".join(lines)

    def _render_telemetry(self) -> str:
        """Render telemetry content (entropy, details, mutation log)."""

        if self.runtime.session is None:
            return ""

        lines: list[str] = []

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
            build_mutation_log_lines(event_log=getattr(self.runtime, "event_log", None))
        )

        return "\n".join(lines)
