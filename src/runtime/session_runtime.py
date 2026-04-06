"""Session runtime command router skeleton with owned graph state."""

from __future__ import annotations

from uuid import UUID

from graph.session_graph import SessionGraph
from models.commands import (
    CommandResult,
    ExportSessionCommand,
    ForkSessionCommand,
    InspectNodeCommand,
    LockEdgeCommand,
    PauseSessionCommand,
    QuitCommand,
    ResumeSessionCommand,
    StartSessionCommand,
    TerminalCommand,
    UnlockEdgeCommand,
)

__all__ = ["SessionRuntime"]


class SessionRuntime:
    """Own the mutable session graph and route commands into handlers."""

    def __init__(self, session_graph: SessionGraph | None = None) -> None:
        self.session_graph = session_graph or SessionGraph()
        self.state_version = 0
        self.session_id: UUID | None = None

    def handle_command(self, command: TerminalCommand) -> CommandResult:
        """Dispatch a terminal command to the matching handler."""

        if isinstance(command, StartSessionCommand):
            return self._handle_start_session(command)

        if isinstance(command, PauseSessionCommand):
            return self._handle_pause_session(command)

        if isinstance(command, ResumeSessionCommand):
            return self._handle_resume_session(command)

        if isinstance(command, LockEdgeCommand):
            return self._handle_lock_edge(command)

        if isinstance(command, UnlockEdgeCommand):
            return self._handle_unlock_edge(command)

        if isinstance(command, ForkSessionCommand):
            return self._handle_fork_session(command)

        if isinstance(command, InspectNodeCommand):
            return self._handle_inspect_node(command)

        if isinstance(command, ExportSessionCommand):
            return self._handle_export_session(command)

        if isinstance(command, QuitCommand):
            return self._handle_quit(command)

        raise ValueError(f"unsupported command type: {command.command_type}")

    def _handle_start_session(self, command: StartSessionCommand) -> CommandResult:
        return self._build_result(command.command_id, "start_session routed")

    def _handle_pause_session(self, command: PauseSessionCommand) -> CommandResult:
        return self._build_result(command.command_id, "pause_session routed")

    def _handle_resume_session(self, command: ResumeSessionCommand) -> CommandResult:
        return self._build_result(command.command_id, "resume_session routed")

    def _handle_lock_edge(self, command: LockEdgeCommand) -> CommandResult:
        return self._build_result(command.command_id, "lock_edge routed")

    def _handle_unlock_edge(self, command: UnlockEdgeCommand) -> CommandResult:
        return self._build_result(command.command_id, "unlock_edge routed")

    def _handle_fork_session(self, command: ForkSessionCommand) -> CommandResult:
        return self._build_result(command.command_id, "fork_session routed")

    def _handle_inspect_node(self, command: InspectNodeCommand) -> CommandResult:
        return self._build_result(command.command_id, "inspect_node routed")

    def _handle_export_session(self, command: ExportSessionCommand) -> CommandResult:
        return self._build_result(command.command_id, "export_session routed")

    def _handle_quit(self, command: QuitCommand) -> CommandResult:
        return self._build_result(command.command_id, "quit routed")

    def _build_result(self, command_id: str, message: str) -> CommandResult:
        return CommandResult(
            command_id=command_id,
            accepted=True,
            session_id=self.session_id,
            state_version=self.state_version,
            message=message,
        )
