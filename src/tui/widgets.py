"""Minimal TUI command helpers for topology controls and session switching."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from textual.timer import Timer
from textual.widgets import Static

from models.commands import (
    CommandResult,
    CommandType,
    ForkSessionCommand,
    ForkSessionPayload,
    LockEdgeCommand,
    LockEdgePayload,
    TerminalCommand,
    UnlockEdgeCommand,
    UnlockEdgePayload,
)

__all__ = [
    "ShortcutFooterBar",
    "SessionSwitcher",
    "handle_fork_request",
    "handle_lock_request",
    "handle_unlock_request",
]


class ShortcutFooterBar(Static):
    """Dedicated footer bar that shows shortcuts and generation status."""

    DEFAULT_CSS = """
    ShortcutFooterBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    """

    _SPINNER_FRAMES = ("|", "/", "-", "\\")

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._is_generating = False
        self._spinner_index = 0
        self._spinner_timer: Timer | None = None

    def on_mount(self) -> None:
        """Render the footer text when mounted."""

        self._update_display()

    def on_unmount(self) -> None:
        """Stop spinner updates when unmounted."""

        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def shortcuts_text(self) -> str:
        """Return the static shortcuts legend shown in the footer."""

        return "s Start   p Pause   r Resume   c Continue"

    def status_text(self) -> str:
        """Return the current runtime status text."""

        if not self._is_generating:
            return "Idle"

        frame = self._SPINNER_FRAMES[self._spinner_index]
        return f"{frame} Generating scene..."

    def advance_spinner_frame(self) -> None:
        """Advance the spinner and redraw the footer."""

        self._spinner_index = (self._spinner_index + 1) % len(self._SPINNER_FRAMES)
        self._update_display()

    def set_generating(self, is_generating: bool) -> None:
        """Toggle generation status and spinner activity."""

        if self._is_generating == is_generating:
            return

        self._is_generating = is_generating
        if is_generating:
            self._spinner_index = 0
            if self.is_mounted and self._spinner_timer is None:
                self._spinner_timer = self.set_interval(
                    0.15,
                    self.advance_spinner_frame,
                )
        elif self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

        self._update_display()

    def _update_display(self) -> None:
        footer_text = f"{self.shortcuts_text()}    {self.status_text()}"
        self.update(footer_text)


class _CommandRuntime(Protocol):
    """Runtime contract for dispatching terminal commands."""

    def handle_command(self, command: TerminalCommand) -> CommandResult:
        """Dispatch a terminal command."""


class _SessionSwitchRuntime(Protocol):
    """Runtime contract for switching an active session."""

    def switch_session(self, session_id: UUID) -> None:
        """Switch the active session."""


def _active_session_id(runtime: _CommandRuntime) -> UUID | None:
    """Return the runtime session identifier when available."""

    session_id = getattr(runtime, "session_id", None)
    return session_id if isinstance(session_id, UUID) else None


def _command_id(prefix: str) -> str:
    """Return a unique command identifier for a UI request."""

    return f"{prefix}-{uuid4().hex}"


def handle_lock_request(runtime: _CommandRuntime, edge_id: str) -> CommandResult:
    """Lock an edge by dispatching a lock-edge command through the runtime."""

    command = LockEdgeCommand(
        command_id=_command_id("ui-lock-edge"),
        session_id=_active_session_id(runtime),
        command_type=CommandType.LOCK_EDGE,
        payload=LockEdgePayload(edge_id=edge_id),
    )
    return runtime.handle_command(command)


def handle_unlock_request(runtime: _CommandRuntime, edge_id: str) -> CommandResult:
    """Unlock an edge by dispatching an unlock-edge command through the runtime."""

    command = UnlockEdgeCommand(
        command_id=_command_id("ui-unlock-edge"),
        session_id=_active_session_id(runtime),
        command_type=CommandType.UNLOCK_EDGE,
        payload=UnlockEdgePayload(edge_id=edge_id),
    )
    return runtime.handle_command(command)


def handle_fork_request(
    runtime: _CommandRuntime,
    fork_label: str | None = None,
) -> CommandResult:
    """Fork the active session by dispatching a fork-session command."""

    command = ForkSessionCommand(
        command_id=_command_id("ui-fork-session"),
        session_id=_active_session_id(runtime),
        command_type=CommandType.FORK_SESSION,
        payload=ForkSessionPayload(fork_label=fork_label),
    )
    return runtime.handle_command(command)


class SessionSwitcher:
    """Thin wrapper around the runtime session switching API."""

    def __init__(self, runtime: _SessionSwitchRuntime) -> None:
        self._runtime = runtime

    def switch_session(self, session_id: UUID) -> None:
        """Switch the active session through the runtime."""

        self._runtime.switch_session(session_id)
