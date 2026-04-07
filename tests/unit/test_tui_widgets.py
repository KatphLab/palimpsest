"""Unit tests for TUI widgets."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from uuid import UUID

from models.commands import (
    CommandType,
    ForkSessionCommand,
    LockEdgeCommand,
    TerminalCommand,
    UnlockEdgeCommand,
)


def _widgets_module() -> ModuleType:
    return import_module("tui.widgets")


class _CommandRuntimeSpy:
    def __init__(self) -> None:
        self.commands: list[TerminalCommand] = []

    def handle_command(self, command: TerminalCommand) -> str:
        self.commands.append(command)
        return "handled"


class _SessionSwitchRuntimeSpy:
    def __init__(self) -> None:
        self.session_ids: list[UUID] = []

    def switch_session(self, session_id: UUID) -> None:
        self.session_ids.append(session_id)


def test_handle_lock_request_routes_lock_edge_command_through_runtime() -> None:
    """Lock helper should build and dispatch a lock-edge command."""

    widgets = _widgets_module()
    runtime = _CommandRuntimeSpy()
    edge_id = "edge-001"

    result = widgets.handle_lock_request(runtime, edge_id)

    assert result == "handled"
    assert len(runtime.commands) == 1

    command = runtime.commands[0]
    assert isinstance(command, LockEdgeCommand)
    assert command.command_type == CommandType.LOCK_EDGE
    assert command.payload.edge_id == edge_id


def test_handle_unlock_request_routes_unlock_edge_command_through_runtime() -> None:
    """Unlock helper should build and dispatch an unlock-edge command."""

    widgets = _widgets_module()
    runtime = _CommandRuntimeSpy()
    edge_id = "edge-002"

    result = widgets.handle_unlock_request(runtime, edge_id)

    assert result == "handled"
    assert len(runtime.commands) == 1

    command = runtime.commands[0]
    assert isinstance(command, UnlockEdgeCommand)
    assert command.command_type == CommandType.UNLOCK_EDGE
    assert command.payload.edge_id == edge_id


def test_handle_fork_request_routes_fork_session_command_through_runtime() -> None:
    """Fork helper should build and dispatch a fork-session command."""

    widgets = _widgets_module()
    runtime = _CommandRuntimeSpy()

    result = widgets.handle_fork_request(runtime, fork_label="branch-a")

    assert result == "handled"
    assert len(runtime.commands) == 1

    command = runtime.commands[0]
    assert isinstance(command, ForkSessionCommand)
    assert command.command_type == CommandType.FORK_SESSION
    assert command.payload.fork_label == "branch-a"


def test_command_helpers_generate_unique_command_ids_per_request() -> None:
    """Each UI helper call should emit a distinct command identifier."""

    widgets = _widgets_module()

    lock_runtime = _CommandRuntimeSpy()
    widgets.handle_lock_request(lock_runtime, "edge-001")
    widgets.handle_lock_request(lock_runtime, "edge-001")

    assert lock_runtime.commands[0].command_id != lock_runtime.commands[1].command_id

    unlock_runtime = _CommandRuntimeSpy()
    widgets.handle_unlock_request(unlock_runtime, "edge-002")
    widgets.handle_unlock_request(unlock_runtime, "edge-002")

    assert (
        unlock_runtime.commands[0].command_id != unlock_runtime.commands[1].command_id
    )

    fork_runtime = _CommandRuntimeSpy()
    widgets.handle_fork_request(fork_runtime, fork_label="branch-a")
    widgets.handle_fork_request(fork_runtime, fork_label="branch-a")

    assert fork_runtime.commands[0].command_id != fork_runtime.commands[1].command_id


def test_session_switcher_delegates_to_runtime_switch_session() -> None:
    """Session switching should use the runtime switch API directly."""

    widgets = _widgets_module()
    runtime = _SessionSwitchRuntimeSpy()
    session_id = UUID(int=1)

    switcher = widgets.SessionSwitcher(runtime=runtime)
    switcher.switch_session(session_id)

    assert runtime.session_ids == [session_id]
