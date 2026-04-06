"""Session runtime command router with owned graph state."""

from __future__ import annotations

import copy
import logging
from collections import deque
from datetime import datetime, timezone
from enum import StrEnum
from threading import Event, Lock, Thread
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field

from agents.scene_agent import SceneAgent
from graph.session_graph import GraphEdge, GraphNode, SessionGraph
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
from models.common import SessionStatus, StrictBaseModel, UTCDateTime
from models.node import SceneNode
from models.session import Session

__all__ = ["SessionRuntime"]

LOGGER = logging.getLogger(__name__)

_DEFAULT_REFRESH_INTERVAL_SECONDS = 0.25
_MAX_RUNTIME_EVENTS = 1000


class _RuntimeEventType(StrEnum):
    """US2 runtime event kinds tracked in memory."""

    ADD_NODE = "add_node"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    REWRITE_NODE = "rewrite_node"
    PRUNE_BRANCH = "prune_branch"
    LOCK_EDGE = "lock_edge"
    UNLOCK_EDGE = "unlock_edge"
    FORK_SESSION = "fork_session"


class _RuntimeEvent(StrictBaseModel):
    """Lightweight runtime event record."""

    sequence: int = Field(ge=1)
    event_type: _RuntimeEventType
    session_id: UUID
    occurred_at: UTCDateTime
    command_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    edge_id: str | None = None
    forked_session_id: UUID | None = None
    parent_session_id: UUID | None = None


class _RuntimeSessionState(StrictBaseModel):
    """In-memory session snapshot paired with its graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: Session
    session_graph: SessionGraph


class SessionRuntime:
    """Own the mutable session graph and route commands into handlers."""

    def __init__(
        self,
        session_graph: SessionGraph | None = None,
        *,
        scene_agent: SceneAgent | None = None,
        refresh_interval_seconds: float = _DEFAULT_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        self.session_graph = session_graph or SessionGraph()
        self.state_version = 0
        self.session_id: UUID | None = None
        self.session: Session | None = None
        self._scene_agent = scene_agent or SceneAgent()
        self._refresh_interval_seconds = refresh_interval_seconds
        self._lock = Lock()
        self._refresh_stop = Event()
        self._refresh_thread: Thread | None = None
        self._session_states: dict[UUID, _RuntimeSessionState] = {}
        self._runtime_event_buffer: deque[_RuntimeEvent] = deque(
            maxlen=_MAX_RUNTIME_EVENTS
        )
        self._runtime_event_sequence = 0

    @property
    def runtime_event_buffer(self) -> tuple[_RuntimeEvent, ...]:
        """Return the in-memory runtime event buffer."""

        return tuple(self._runtime_event_buffer)

    def available_session_ids(self) -> tuple[UUID, ...]:
        """Return the known session identifiers in creation order."""

        return tuple(self._session_states.keys())

    def activate_session(self, session_id: UUID) -> None:
        """Switch the runtime foreground session to a stored session."""

        with self._lock:
            self._activate_session(session_id)

    def switch_session(self, session_id: UUID) -> None:
        """Alias for activating a stored session."""

        self.activate_session(session_id)

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
        with self._lock:
            if command.session_id is not None:
                raise ValueError("start_session must not include a session_id")

            if self.session is not None:
                raise ValueError("a session is already active")

            now = datetime.now(timezone.utc)
            session_id = uuid4()
            self.session = Session(
                session_id=session_id,
                status=SessionStatus.CREATED,
                seed_text=command.payload.seed_text,
                graph_version=0,
                active_node_ids=[],
                created_at=now,
                updated_at=now,
            )
            self.session_id = session_id

            self._scene_agent.bootstrap_session(
                self.session,
                self.session_graph,
                activated_at=now,
            )
            self._session_states[session_id] = _RuntimeSessionState(
                session=self.session,
                session_graph=self.session_graph,
            )
            self.state_version = 1
            self._ensure_refresh_loop()

            LOGGER.info("started session %s", session_id)
            return self._build_result(command.command_id, "start_session accepted")

    def _handle_pause_session(self, command: PauseSessionCommand) -> CommandResult:
        with self._lock:
            self._require_active_session(SessionStatus.RUNNING)
            assert self.session is not None

            self.session.status = SessionStatus.PAUSED
            self.session.updated_at = datetime.now(timezone.utc)
            LOGGER.info("paused session %s", self.session_id)
            return self._build_result(command.command_id, "pause_session accepted")

    def _handle_resume_session(self, command: ResumeSessionCommand) -> CommandResult:
        with self._lock:
            if self.session is None or self.session_id is None:
                raise ValueError("no active session exists")

            # If session is already running, return a rejected result instead of error
            if self.session.status == SessionStatus.RUNNING:
                return CommandResult(
                    command_id=command.command_id,
                    accepted=False,
                    session_id=self.session_id,
                    state_version=self.state_version,
                    message="Session is already running",
                )

            if self.session.status != SessionStatus.PAUSED:
                raise ValueError(
                    f"session must be {SessionStatus.PAUSED} to handle this command"
                )

            self.session.status = SessionStatus.RUNNING
            self.session.updated_at = datetime.now(timezone.utc)
            self.state_version += 1
            LOGGER.info("resumed session %s", self.session_id)
            return self._build_result(command.command_id, "resume_session accepted")

    def _handle_lock_edge(self, command: LockEdgeCommand) -> CommandResult:
        with self._lock:
            self._require_active_session(SessionStatus.RUNNING)
            self._require_command_session_matches_active(command.session_id)
            assert self.session is not None

            self.session_graph.lock_edge(command.payload.edge_id)
            self.session.updated_at = datetime.now(timezone.utc)
            self.session.graph_version += 1
            self.state_version += 1
            self._append_runtime_event(
                event_type=_RuntimeEventType.LOCK_EDGE,
                command_id=command.command_id,
                session_id=self.session_id,
                edge_id=command.payload.edge_id,
                message="lock_edge accepted",
            )
            LOGGER.info(
                "locked edge %s in session %s", command.payload.edge_id, self.session_id
            )
            return self._build_result(command.command_id, "lock_edge accepted")

    def _handle_unlock_edge(self, command: UnlockEdgeCommand) -> CommandResult:
        with self._lock:
            self._require_active_session(SessionStatus.RUNNING)
            self._require_command_session_matches_active(command.session_id)
            assert self.session is not None

            self.session_graph.unlock_edge(command.payload.edge_id)
            self.session.updated_at = datetime.now(timezone.utc)
            self.session.graph_version += 1
            self.state_version += 1
            self._append_runtime_event(
                event_type=_RuntimeEventType.UNLOCK_EDGE,
                command_id=command.command_id,
                session_id=self.session_id,
                edge_id=command.payload.edge_id,
                message="unlock_edge accepted",
            )
            LOGGER.info(
                "unlocked edge %s in session %s",
                command.payload.edge_id,
                self.session_id,
            )
            return self._build_result(command.command_id, "unlock_edge accepted")

    def _handle_fork_session(self, command: ForkSessionCommand) -> CommandResult:
        with self._lock:
            self._require_active_session(SessionStatus.RUNNING)
            self._require_command_session_matches_active(command.session_id)
            assert self.session is not None
            assert self.session_id is not None

            now = datetime.now(timezone.utc)
            fork_session_id = uuid4()
            forked_session = self.session.model_copy(deep=True)
            forked_session.session_id = fork_session_id
            forked_session.parent_session_id = self.session_id
            forked_session.created_at = now
            forked_session.updated_at = now

            forked_graph = copy.deepcopy(self.session_graph)
            self._retarget_graph_session_ids(forked_graph, fork_session_id)
            self._session_states[fork_session_id] = _RuntimeSessionState(
                session=forked_session,
                session_graph=forked_graph,
            )

            self._scene_agent.refresh_visible_state(
                self.session,
                self.session_graph,
                refreshed_at=now,
            )
            self.session.updated_at = now
            self.state_version += 1
            self._append_runtime_event(
                event_type=_RuntimeEventType.FORK_SESSION,
                command_id=command.command_id,
                session_id=self.session_id,
                message="fork_session accepted",
                forked_session_id=fork_session_id,
                parent_session_id=self.session_id,
            )
            LOGGER.info(
                "forked session %s from parent %s",
                fork_session_id,
                self.session_id,
            )
            return CommandResult(
                command_id=command.command_id,
                accepted=True,
                session_id=fork_session_id,
                state_version=self.state_version,
                message="fork_session accepted",
            )

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

    def _require_active_session(self, required_status: SessionStatus) -> None:
        if self.session is None or self.session_id is None:
            raise ValueError("no active session exists")

        if self.session.status != required_status:
            raise ValueError(
                f"session must be {required_status} to handle this command"
            )

    def _require_command_session_matches_active(
        self, command_session_id: UUID | None
    ) -> None:
        if command_session_id is None:
            return

        if self.session_id is None or command_session_id != self.session_id:
            raise ValueError("command session_id must match the active session")

    def _activate_session(self, session_id: UUID) -> None:
        session_state = self._session_states.get(session_id)
        if session_state is None:
            raise ValueError(f"unknown session '{session_id}'")

        self.session_id = session_id
        self.session = session_state.session
        self.session_graph = session_state.session_graph

    def _append_runtime_event(
        self,
        *,
        event_type: _RuntimeEventType,
        command_id: str,
        session_id: UUID | None,
        message: str,
        edge_id: str | None = None,
        forked_session_id: UUID | None = None,
        parent_session_id: UUID | None = None,
    ) -> None:
        if session_id is None:
            raise ValueError("no active session exists")

        self._runtime_event_sequence += 1
        self._runtime_event_buffer.append(
            _RuntimeEvent(
                sequence=self._runtime_event_sequence,
                event_type=event_type,
                session_id=session_id,
                occurred_at=datetime.now(timezone.utc),
                command_id=command_id,
                message=message,
                edge_id=edge_id,
                forked_session_id=forked_session_id,
                parent_session_id=parent_session_id,
            )
        )

    def _retarget_graph_session_ids(
        self, session_graph: SessionGraph, session_id: UUID
    ) -> None:
        for _, node_data in session_graph.graph.nodes(data=True):
            graph_node = node_data.get("node")
            if isinstance(graph_node, GraphNode):
                node_data["node"] = graph_node.model_copy(
                    update={"session_id": session_id}
                )

            scene_node = node_data.get("scene_node")
            if isinstance(scene_node, SceneNode):
                node_data["scene_node"] = scene_node.model_copy(
                    update={"session_id": session_id}
                )

        for _, _, _, edge_data in session_graph.graph.edges(keys=True, data=True):
            graph_edge = edge_data.get("edge")
            if isinstance(graph_edge, GraphEdge):
                edge_data["edge"] = graph_edge.model_copy(
                    update={"session_id": session_id}
                )

    def _ensure_refresh_loop(self) -> None:
        if self._refresh_thread is not None:
            return

        self._refresh_thread = Thread(
            target=self._refresh_loop,
            name="session-refresh-loop",
            daemon=True,
        )
        self._refresh_thread.start()

    def _refresh_loop(self) -> None:
        while not self._refresh_stop.wait(self._refresh_interval_seconds):
            with self._lock:
                if self.session is None or self.session.status != SessionStatus.RUNNING:
                    continue

                self._scene_agent.refresh_visible_state(
                    self.session,
                    self.session_graph,
                    refreshed_at=datetime.now(timezone.utc),
                )
