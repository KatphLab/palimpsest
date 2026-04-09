"""Session runtime command router with owned graph state."""

from __future__ import annotations

import copy
import errno
import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from threading import Lock
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field

from agents.llm_mutation_proposer import LLMMutationProposer, LLMMutationProposerError
from agents.mutation_agent import MutationAgent
from agents.mutation_engine import MutationEngine
from agents.scene_agent import SceneAgent
from config.env import (
    _DEFAULT_GLOBAL_CONSISTENCY_CHECK_INTERVAL_MS,
    _DEFAULT_GLOBAL_MUTATION_STORM_THRESHOLD,
    _DEFAULT_MUTATION_BURST_TRIGGER_COUNT,
    _DEFAULT_MUTATION_BURST_WINDOW_SECONDS,
    _DEFAULT_SESSION_MUTATION_COOLDOWN_MS,
)
from graph.session_graph import SessionGraph
from graph.utils import get_graph_node, get_scene_node
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
from models.common import (
    BudgetTelemetry,
    CheckStatus,
    CoherenceSnapshot,
    DriftCategory,
    EventOutcome,
    MutationActionType,
    MutationEventKind,
    ProtectionReason,
    SafetyCheckResult,
    SessionStatus,
    StrictBaseModel,
    TerminationVoteState,
    UTCDateTime,
)
from models.events import EventType, MutationStreamEvent, SessionEvent
from models.execution import ExecutionStatus
from models.graph import GraphEdge, GraphNode
from models.graph_session import GraphSession
from models.mutation import MutationDecision, MutationProposal
from models.node import SceneNode
from models.requests import (
    ForkFromCurrentNodeRequest,
    GraphNavigationDirection,
    GraphSwitchRequest,
)
from models.responses import MultiGraphStatusSnapshot, RunningState
from models.session import Session
from runtime.consistency import (
    ConsistencyGuardrailState,
    mark_global_consistency_check_completed,
    prune_consistency_guardrails,
    record_consistency_outcome,
    should_run_global_consistency_check,
)
from runtime.event_log import EventLog
from runtime.exporter import build_export_artifact, write_export_artifact
from runtime.graph_registry import GraphNotFoundError, GraphRegistry, NoActiveGraphError
from utils.narrative_context_builder import NarrativeContextBuilder
from utils.time import utc_now

__all__ = ["SessionRuntime"]

LOGGER = logging.getLogger(__name__)

_MAX_RUNTIME_EVENTS = 1000
_NO_ACTIVE_SESSION_ERROR = "no active session exists"
_COMMAND_SESSION_MISMATCH_ERROR = "command session_id must match the active session"
_ACTIVE_SESSION_STATE_UNAVAILABLE_ERROR = "active session state is unavailable"
_OUTPUT_PATH_NOT_WRITABLE_ERROR = "output path is not writable"
_RUNTIME_MUTATION_ORCHESTRATED_KEY = "runtime_mutation_orchestrated"
_RUNTIME_MUTATION_RESOLVED_KEY = "runtime_mutation_cycle_resolved"
_MUTATION_CYCLE_RESOLVED_ERROR = "mutation cycle already resolved"
_RUNTIME_SESSION_MUTATION_COOLDOWN = timedelta(
    milliseconds=_DEFAULT_SESSION_MUTATION_COOLDOWN_MS
)
_RUNTIME_MUTATION_PROPOSER_FAILURE_THRESHOLD = 2
_RUNTIME_MUTATION_PROPOSER_BACKOFF_DURATION = timedelta(seconds=30)
_RUNTIME_MUTATION_BURST_WINDOW = timedelta(
    seconds=_DEFAULT_MUTATION_BURST_WINDOW_SECONDS
)
_RUNTIME_MUTATION_BURST_TRIGGER_COUNT = _DEFAULT_MUTATION_BURST_TRIGGER_COUNT
_RUNTIME_GLOBAL_MUTATION_STORM_THRESHOLD = _DEFAULT_GLOBAL_MUTATION_STORM_THRESHOLD
_RUNTIME_GLOBAL_CONSISTENCY_CHECK_INTERVAL = timedelta(
    milliseconds=_DEFAULT_GLOBAL_CONSISTENCY_CHECK_INTERVAL_MS
)
_RUNTIME_BUDGET_WARNING_RATIO = Decimal("0.85")

_SESSION_GRAPH_ADD_NODE_ORIGINAL: Callable[[SessionGraph, GraphNode], None] | None = (
    None
)
_SESSION_GRAPH_ADD_EDGE_ORIGINAL: Callable[[SessionGraph, GraphEdge], None] | None = (
    None
)
_SESSION_GRAPH_GET_EDGE_ORIGINAL: (
    Callable[[SessionGraph, str], GraphEdge | None] | None
) = None
_SESSION_GRAPH_REMOVE_EDGE_ORIGINAL: Callable[[SessionGraph, str], None] | None = None
_SESSION_GRAPH_MUTATION_HOOKS_INSTALLED = False


def _is_non_writable_export_error(error: OSError) -> bool:
    """Return whether an OS error represents a non-writable output path."""

    if isinstance(error, PermissionError):
        return True

    return error.errno in {errno.EACCES, errno.EPERM, errno.EROFS}


def _is_runtime_orchestrated(session_graph: SessionGraph) -> bool:
    return bool(session_graph.graph.graph.get(_RUNTIME_MUTATION_ORCHESTRATED_KEY))


def _is_cycle_resolved(session_graph: SessionGraph) -> bool:
    return bool(session_graph.graph.graph.get(_RUNTIME_MUTATION_RESOLVED_KEY))


def _raise_if_cycle_resolved(session_graph: SessionGraph) -> None:
    if _is_runtime_orchestrated(session_graph) and _is_cycle_resolved(session_graph):
        raise ValueError(_MUTATION_CYCLE_RESOLVED_ERROR)


def _guarded_add_node(session_graph: SessionGraph, node: GraphNode) -> None:
    _raise_if_cycle_resolved(session_graph)
    assert _SESSION_GRAPH_ADD_NODE_ORIGINAL is not None
    _SESSION_GRAPH_ADD_NODE_ORIGINAL(session_graph, node)


def _guarded_add_edge(session_graph: SessionGraph, edge: GraphEdge) -> None:
    _raise_if_cycle_resolved(session_graph)
    assert _SESSION_GRAPH_ADD_EDGE_ORIGINAL is not None
    _SESSION_GRAPH_ADD_EDGE_ORIGINAL(session_graph, edge)


def _guarded_get_edge(session_graph: SessionGraph, edge_id: str) -> GraphEdge | None:
    assert _SESSION_GRAPH_GET_EDGE_ORIGINAL is not None
    edge = _SESSION_GRAPH_GET_EDGE_ORIGINAL(session_graph, edge_id)
    if edge is None:
        return None

    if not _is_runtime_orchestrated(session_graph) or not _is_cycle_resolved(
        session_graph
    ):
        return edge

    protected_reason = edge.protected_reason or ProtectionReason.SAFETY_GUARD
    return edge.model_copy(
        update={"locked": True, "protected_reason": protected_reason}
    )


def _guarded_remove_edge(session_graph: SessionGraph, edge_id: str) -> None:
    _raise_if_cycle_resolved(session_graph)
    assert _SESSION_GRAPH_REMOVE_EDGE_ORIGINAL is not None
    _SESSION_GRAPH_REMOVE_EDGE_ORIGINAL(session_graph, edge_id)

    if _is_runtime_orchestrated(session_graph):
        session_graph.graph.graph[_RUNTIME_MUTATION_RESOLVED_KEY] = True


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
    GRAPH_SWITCH = "graph_switch"


class _RuntimeEvent(StrictBaseModel):
    """Lightweight runtime event record."""

    sequence: int = Field(ge=1)
    event_type: _RuntimeEventType | MutationEventKind | EventType
    session_id: UUID
    occurred_at: UTCDateTime
    command_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    edge_id: str | None = None
    forked_session_id: UUID | None = None
    parent_session_id: UUID | None = None


class _RuntimeSessionState(StrictBaseModel):
    """In-memory session snapshot paired with its graph and guard state."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: Session
    session_graph: SessionGraph
    event_log: EventLog
    node_cooldowns: dict[str, UTCDateTime] = Field(default_factory=dict)
    recent_mutation_times: list[UTCDateTime] = Field(default_factory=list)
    burst_check_pending: bool = False
    burst_cooldown_until: UTCDateTime | None = None
    mutation_proposer_failure_count: int = 0
    mutation_proposer_backoff_until: UTCDateTime | None = None


def _install_session_graph_mutation_hooks() -> None:
    """Patch session-graph topology methods with runtime-cycle guards."""

    global _SESSION_GRAPH_ADD_NODE_ORIGINAL
    global _SESSION_GRAPH_ADD_EDGE_ORIGINAL
    global _SESSION_GRAPH_GET_EDGE_ORIGINAL
    global _SESSION_GRAPH_REMOVE_EDGE_ORIGINAL
    global _SESSION_GRAPH_MUTATION_HOOKS_INSTALLED

    if _SESSION_GRAPH_MUTATION_HOOKS_INSTALLED:
        return

    _SESSION_GRAPH_ADD_NODE_ORIGINAL = SessionGraph.add_node
    _SESSION_GRAPH_ADD_EDGE_ORIGINAL = SessionGraph.add_edge
    _SESSION_GRAPH_GET_EDGE_ORIGINAL = SessionGraph.get_edge
    _SESSION_GRAPH_REMOVE_EDGE_ORIGINAL = SessionGraph.remove_edge

    setattr(SessionGraph, "add_node", _guarded_add_node)
    setattr(SessionGraph, "add_edge", _guarded_add_edge)
    setattr(SessionGraph, "get_edge", _guarded_get_edge)
    setattr(SessionGraph, "remove_edge", _guarded_remove_edge)
    _SESSION_GRAPH_MUTATION_HOOKS_INSTALLED = True


def _mark_runtime_mutation_graph(session_graph: SessionGraph) -> None:
    """Mark a graph as owned by the runtime mutation orchestrator."""

    session_graph.graph.graph[_RUNTIME_MUTATION_ORCHESTRATED_KEY] = True
    session_graph.graph.graph[_RUNTIME_MUTATION_RESOLVED_KEY] = False


def _reset_runtime_mutation_cycle(session_graph: SessionGraph) -> None:
    """Allow a fresh autonomous cycle to inspect the live graph."""

    if session_graph.graph.graph.get(_RUNTIME_MUTATION_ORCHESTRATED_KEY):
        session_graph.graph.graph[_RUNTIME_MUTATION_RESOLVED_KEY] = False


def _seal_runtime_mutation_cycle(session_graph: SessionGraph) -> None:
    """Close the current autonomous cycle to subsequent mutations."""

    if session_graph.graph.graph.get(_RUNTIME_MUTATION_ORCHESTRATED_KEY):
        session_graph.graph.graph[_RUNTIME_MUTATION_RESOLVED_KEY] = True


def _execution_status_from_session_status(status: SessionStatus) -> ExecutionStatus:
    """Map runtime session status to GraphSession execution status."""

    if status is SessionStatus.RUNNING:
        return ExecutionStatus.RUNNING

    if status is SessionStatus.PAUSED:
        return ExecutionStatus.PAUSED

    if status is SessionStatus.FAILED:
        return ExecutionStatus.FAILED

    if status in {SessionStatus.TERMINATING, SessionStatus.TERMINATED}:
        return ExecutionStatus.COMPLETED

    return ExecutionStatus.IDLE


class SessionRuntime:
    """Own the mutable session graph and route commands into handlers."""

    def __init__(
        self,
        session_graph: SessionGraph | None = None,
        *,
        scene_agent: SceneAgent | None = None,
        mutation_proposer: LLMMutationProposer | None = None,
        graph_registry: GraphRegistry | None = None,
    ) -> None:
        _install_session_graph_mutation_hooks()
        self.session_graph = session_graph or SessionGraph()
        _mark_runtime_mutation_graph(self.session_graph)
        self.state_version = 0
        self.session_id: UUID | None = None
        self.session: Session | None = None
        self._scene_agent = scene_agent or SceneAgent()
        self._mutation_proposer = mutation_proposer or LLMMutationProposer()
        self._narrative_context_builder = NarrativeContextBuilder()
        self._mutation_engine = MutationEngine()
        self._mutation_agent = MutationAgent()
        self._lock = Lock()
        self._session_states: dict[UUID, _RuntimeSessionState] = {}
        self._runtime_event_buffer: deque[_RuntimeEvent] = deque(
            maxlen=_MAX_RUNTIME_EVENTS
        )
        self._runtime_event_sequence = 0
        self._mutation_cycle_sequence = 0
        self._mutation_cooldown = _RUNTIME_SESSION_MUTATION_COOLDOWN
        self._mutation_proposer_failure_threshold = (
            _RUNTIME_MUTATION_PROPOSER_FAILURE_THRESHOLD
        )
        self._mutation_proposer_backoff_duration = (
            _RUNTIME_MUTATION_PROPOSER_BACKOFF_DURATION
        )
        self._mutation_burst_window = _RUNTIME_MUTATION_BURST_WINDOW
        self._mutation_burst_trigger_count = _RUNTIME_MUTATION_BURST_TRIGGER_COUNT
        self._global_mutation_storm_threshold = _RUNTIME_GLOBAL_MUTATION_STORM_THRESHOLD
        self._global_consistency_check_interval = (
            _RUNTIME_GLOBAL_CONSISTENCY_CHECK_INTERVAL
        )
        self.graph_registry = (
            graph_registry if graph_registry is not None else GraphRegistry()
        )

    @property
    def runtime_event_buffer(self) -> tuple[_RuntimeEvent, ...]:
        """Return the in-memory runtime event buffer."""

        return tuple(self._runtime_event_buffer)

    @property
    def event_log(self) -> EventLog | None:
        """Return the active session event log when one exists."""

        if self.session_id is None:
            return None

        session_state = self._session_states.get(self.session_id)
        if session_state is None:
            return None

        return session_state.event_log

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

            now = utc_now()
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
            _mark_runtime_mutation_graph(self.session_graph)
            self._session_states[session_id] = _RuntimeSessionState(
                session=self.session,
                session_graph=self.session_graph,
                event_log=EventLog(session_id=session_id, latest_sequence=0, events=[]),
            )
            self._append_session_event(
                session_id=session_id,
                event_type=EventType.SESSION_STARTED,
                command_id=command.command_id,
                message="session started",
                target_ids=list(self.session.active_node_ids),
                actor_id="session-runtime",
            )
            self._synchronize_active_graph_session(create_if_missing=True)
            self.state_version = 1

            LOGGER.info("started session %s", session_id)
            return self._build_result(command.command_id, "start_session accepted")

    def _handle_pause_session(self, command: PauseSessionCommand) -> CommandResult:
        with self._lock:
            self._require_active_session(SessionStatus.RUNNING)
            assert self.session is not None

            self.session.status = SessionStatus.PAUSED
            self.session.updated_at = utc_now()
            self._synchronize_active_graph_session(create_if_missing=True)
            LOGGER.info("paused session %s", self.session_id)
            return self._build_result(command.command_id, "pause_session accepted")

    def _handle_resume_session(self, command: ResumeSessionCommand) -> CommandResult:
        with self._lock:
            if self.session is None or self.session_id is None:
                raise ValueError(_NO_ACTIVE_SESSION_ERROR)

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
            self.session.updated_at = utc_now()
            self._synchronize_active_graph_session(create_if_missing=True)
            self.state_version += 1
            LOGGER.info("resumed session %s", self.session_id)
            return self._build_result(command.command_id, "resume_session accepted")

    def _handle_lock_edge(self, command: LockEdgeCommand) -> CommandResult:
        with self._lock:
            try:
                self._require_active_session(SessionStatus.RUNNING)
                self._require_command_session_matches_active(command.session_id)
            except ValueError as error:
                rejected_result = self._build_precondition_rejection(
                    command.command_id,
                    error,
                )
                if rejected_result is not None:
                    return rejected_result
                raise

            assert self.session is not None

            self.session_graph.lock_edge(command.payload.edge_id)
            self.session.updated_at = utc_now()
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
            try:
                self._require_active_session(SessionStatus.RUNNING)
                self._require_command_session_matches_active(command.session_id)
            except ValueError as error:
                rejected_result = self._build_precondition_rejection(
                    command.command_id,
                    error,
                )
                if rejected_result is not None:
                    return rejected_result
                raise

            assert self.session is not None

            self.session_graph.unlock_edge(command.payload.edge_id)
            self.session.updated_at = utc_now()
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

            now = utc_now()
            fork_session_id = uuid4()
            forked_session = self.session.model_copy(deep=True)
            forked_session.session_id = fork_session_id
            forked_session.parent_session_id = self.session_id
            forked_session.created_at = now
            forked_session.updated_at = now

            forked_graph = copy.deepcopy(self.session_graph)
            self._retarget_graph_session_ids(forked_graph, fork_session_id)
            _mark_runtime_mutation_graph(forked_graph)
            _reset_runtime_mutation_cycle(forked_graph)
            active_state = self._session_states[self.session_id]
            self._session_states[fork_session_id] = _RuntimeSessionState(
                session=forked_session,
                session_graph=forked_graph,
                event_log=copy.deepcopy(active_state.event_log),
                node_cooldowns=dict(active_state.node_cooldowns),
                recent_mutation_times=list(active_state.recent_mutation_times),
                burst_check_pending=active_state.burst_check_pending,
                burst_cooldown_until=active_state.burst_cooldown_until,
                mutation_proposer_failure_count=active_state.mutation_proposer_failure_count,
                mutation_proposer_backoff_until=active_state.mutation_proposer_backoff_until,
            )
            self._scene_agent.bind_session_graph(forked_session, forked_graph)

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
        with self._lock:
            try:
                if self.session is None or self.session_id is None:
                    raise ValueError(_NO_ACTIVE_SESSION_ERROR)

                self._require_command_session_matches_active(command.session_id)
            except ValueError as error:
                rejected_result = self._build_precondition_rejection(
                    command.command_id,
                    error,
                )
                if rejected_result is not None:
                    return rejected_result
                raise

            self._require_inspectable_node(command.payload.node_id)
            assert self.session is not None

            graph_node = get_graph_node(self.session_graph, command.payload.node_id)
            scene_node = get_scene_node(self.session_graph, command.payload.node_id)
            assert graph_node is not None
            assert scene_node is not None

            chronology = " -> ".join(self.session.active_node_ids) or "unknown"
            last_activated_at = (
                scene_node.last_activated_at.isoformat()
                if scene_node.last_activated_at is not None
                else "unknown"
            )
            drift_category = scene_node.drift_category or DriftCategory.STABLE
            message = (
                "inspect_node accepted: "
                f"node_id={graph_node.node_id}; "
                f"entropy={scene_node.entropy_score:.2f}; "
                f"drift={drift_category.value}; "
                f"activation_count={scene_node.activation_count}; "
                f"last_activated_at={last_activated_at}; "
                f"chronology={chronology}; "
                f"session_start={self.session.created_at.isoformat()}; "
                "source=start_session accepted"
            )
            return CommandResult(
                command_id=command.command_id,
                accepted=True,
                session_id=self.session_id,
                state_version=self.state_version,
                message=message,
            )

    def _handle_export_session(self, command: ExportSessionCommand) -> CommandResult:
        with self._lock:
            try:
                if self.session is None or self.session_id is None:
                    raise ValueError(_NO_ACTIVE_SESSION_ERROR)

                self._require_command_session_matches_active(command.session_id)
            except ValueError as error:
                rejected_result = self._build_precondition_rejection(
                    command.command_id,
                    error,
                )
                if rejected_result is not None:
                    return rejected_result
                raise

            assert self.session is not None
            assert self.session_id is not None

            now = utc_now()
            session_snapshot = self.session.snapshot(captured_at=now)
            session_state = self._session_states.get(self.session_id)
            if session_state is None:
                return self._build_rejected_result(
                    command.command_id,
                    _ACTIVE_SESSION_STATE_UNAVAILABLE_ERROR,
                )

            artifact = build_export_artifact(
                session_snapshot=session_snapshot,
                session_graph=self.session_graph,
                events=session_state.event_log.read().events,
                exported_at=now,
            )

            try:
                written_path = write_export_artifact(
                    command.payload.output_path,
                    artifact,
                )
            except ValueError as error:
                return CommandResult(
                    command_id=command.command_id,
                    accepted=False,
                    session_id=self.session_id,
                    state_version=self.state_version,
                    message=str(error),
                )
            except OSError as error:
                if _is_non_writable_export_error(error):
                    return self._build_rejected_result(
                        command.command_id,
                        _OUTPUT_PATH_NOT_WRITABLE_ERROR,
                    )
                raise

            self._append_session_event(
                session_id=self.session_id,
                event_type=EventType.EXPORT_CREATED,
                command_id=command.command_id,
                message=f"export_session accepted: wrote {written_path}",
                actor_id="session-runtime",
            )
            return CommandResult(
                command_id=command.command_id,
                accepted=True,
                session_id=self.session_id,
                state_version=self.state_version,
                message=f"export_session accepted: wrote {written_path}",
            )

    def _handle_quit(self, command: QuitCommand) -> CommandResult:
        return self._build_result(command.command_id, "quit routed")

    def run_mutation_cycle(self) -> MutationDecision | None:
        """Execute one autonomous mutation cycle for the active session."""

        with self._lock:
            decision = self._run_mutation_cycle_locked()
            self._synchronize_active_graph_session(create_if_missing=True)
            return decision

    def advance_session_cycle(self) -> MutationDecision | None:
        """Advance one manual session step by refreshing state and mutating once."""

        with self._lock:
            if self.session is None or self.session_id is None:
                return None

            if self.session.status != SessionStatus.RUNNING:
                return None

            self._scene_agent.refresh_visible_state(
                self.session,
                self.session_graph,
                refreshed_at=utc_now(),
            )
            decision = self._run_mutation_cycle_locked()
            self._synchronize_active_graph_session(create_if_missing=True)
            return decision

    def _synchronize_active_graph_session(self, *, create_if_missing: bool) -> None:
        """Mirror active runtime session state into the graph registry."""

        if self.session is None or self.session_id is None:
            return

        graph_id = str(self.session_id)
        current_node_id = (
            self.session.active_node_ids[-1] if self.session.active_node_ids else None
        )
        execution_status = _execution_status_from_session_status(self.session.status)
        now = utc_now()

        try:
            active_graph = self.graph_registry.get_session(graph_id)
        except GraphNotFoundError:
            if not create_if_missing:
                return

            self.graph_registry.register_session(
                GraphSession(
                    graph_id=graph_id,
                    current_node_id=current_node_id,
                    execution_status=execution_status,
                    is_active=False,
                    last_activity_at=now,
                )
            )
            return

        updated_graph = active_graph.model_copy(
            update={
                "current_node_id": current_node_id,
                "execution_status": execution_status,
                "last_activity_at": now,
            }
        )
        self.graph_registry.update_session(updated_graph)

    def _build_result(self, command_id: str, message: str) -> CommandResult:
        return CommandResult(
            command_id=command_id,
            accepted=True,
            session_id=self.session_id,
            state_version=self.state_version,
            message=message,
        )

    def _build_rejected_result(self, command_id: str, message: str) -> CommandResult:
        """Build a deterministic rejected command result envelope."""

        return CommandResult(
            command_id=command_id,
            accepted=False,
            session_id=self.session_id,
            state_version=self.state_version,
            message=message,
        )

    def _build_precondition_rejection(
        self,
        command_id: str,
        error: ValueError,
    ) -> CommandResult | None:
        """Translate known runtime precondition errors into rejected results."""

        message = str(error)
        if message in {_NO_ACTIVE_SESSION_ERROR, _COMMAND_SESSION_MISMATCH_ERROR}:
            return self._build_rejected_result(command_id, message)

        return None

    def _run_mutation_cycle_locked(self) -> MutationDecision | None:
        if self.session is None or self.session_id is None:
            return None

        if self.session.status != SessionStatus.RUNNING:
            return None

        session_state = self._session_states.get(self.session_id)
        if session_state is None:
            return None

        now = utc_now()
        if (
            self.session.termination is not None
            and self.session.termination.termination_reached
        ):
            self.session.status = SessionStatus.TERMINATING
            self.session.updated_at = now
            self.state_version += 1
            return None

        self._prune_runtime_guardrails(session_state, now)
        self._maybe_run_global_consistency_check(session_state, now)
        self._emit_budget_telemetry_events()

        _reset_runtime_mutation_cycle(self.session_graph)
        try:
            candidate_id = self._select_activation_candidate()
            if candidate_id is None:
                self._append_runtime_event(
                    event_type=MutationEventKind.VETOED,
                    command_id="mutation-cycle-skip-no-candidate",
                    session_id=self.session_id,
                    message="mutation skipped: no activation candidate",
                )
                return None

            proposal, failure_decision = self._propose_llm_mutation(
                activation_candidate_id=candidate_id,
                session_state=session_state,
                now=now,
            )
            if failure_decision is not None:
                return failure_decision

            if proposal is None:
                return None

            self._append_mutation_lifecycle_event(
                proposal=proposal,
                event_type=MutationEventKind.PROPOSED,
                message="mutation proposed",
            )

            if self._is_burst_cooldown_active(session_state, now):
                self._append_mutation_lifecycle_event(
                    proposal=proposal,
                    event_type=MutationEventKind.COOLED_DOWN,
                    message="mutation cooled down",
                )
                return None

            if self._is_node_cooling_down(session_state, candidate_id, now):
                self._append_mutation_lifecycle_event(
                    proposal=proposal,
                    event_type=MutationEventKind.COOLED_DOWN,
                    message="mutation cooled down",
                )
                return None

            decision = self._mutation_agent.review_proposal(
                proposal,
                self.session_graph,
            )

            if decision.accepted:
                self._mutation_agent.apply_decision(decision, self.session_graph)
                self.session.updated_at = now
                self.session.graph_version += 1
                self.state_version += 1
                self._record_runtime_mutation_guardrails(
                    session_state,
                    candidate_id=candidate_id,
                    resolved_at=now,
                    accepted=True,
                )
                self._append_mutation_lifecycle_event(
                    proposal=proposal,
                    event_type=MutationEventKind.APPLIED,
                    message="mutation applied",
                )
            else:
                self._record_runtime_mutation_guardrails(
                    session_state,
                    candidate_id=candidate_id,
                    resolved_at=now,
                    accepted=False,
                )
                self._append_mutation_lifecycle_event(
                    proposal=proposal,
                    event_type=MutationEventKind.REJECTED,
                    message=(
                        f"mutation rejected: {decision.rejected_reason or 'unknown'}"
                    ),
                )
            return decision
        finally:
            _seal_runtime_mutation_cycle(self.session_graph)

    def _select_activation_candidate(self) -> str | None:
        if self.session is None or self.session_id is None:
            return None

        activation_candidate_id = self._mutation_engine.select_activation_candidate(
            self.session,
            self.session_graph,
            activated_at=utc_now(),
        )
        if activation_candidate_id is None:
            return None

        candidate_id = activation_candidate_id.strip()
        return candidate_id or None

    def _next_mutation_cycle_decision_id(self) -> str:
        """Allocate the next synthetic mutation-cycle decision identifier."""

        self._mutation_cycle_sequence += 1
        return f"mutation-cycle-{self._mutation_cycle_sequence:03d}"

    def _is_mutation_proposer_backoff_active(
        self, session_state: _RuntimeSessionState, now: datetime
    ) -> bool:
        """Return whether the proposer circuit breaker is currently open."""

        backoff_until = session_state.mutation_proposer_backoff_until
        return backoff_until is not None and now < backoff_until

    def _record_mutation_proposer_failure(
        self, session_state: _RuntimeSessionState, *, now: datetime
    ) -> None:
        """Record a proposer failure and open backoff when needed."""

        session_state.mutation_proposer_failure_count += 1
        if (
            session_state.mutation_proposer_failure_count
            >= self._mutation_proposer_failure_threshold
        ):
            session_state.mutation_proposer_backoff_until = (
                now + self._mutation_proposer_backoff_duration
            )

    def _reset_mutation_proposer_failure_state(
        self, session_state: _RuntimeSessionState
    ) -> None:
        """Clear proposer failure counters after a successful proposal."""

        session_state.mutation_proposer_failure_count = 0
        session_state.mutation_proposer_backoff_until = None

    def _build_mutation_failure_proposal(
        self,
        *,
        activation_candidate_id: str,
        decision_id: str,
    ) -> MutationProposal:
        """Build a synthetic no-op proposal for failure telemetry."""

        if self.session_id is None:
            raise ValueError(_NO_ACTIVE_SESSION_ERROR)

        return MutationProposal(
            decision_id=decision_id,
            session_id=self.session_id,
            actor_node_id=activation_candidate_id,
            target_ids=[activation_candidate_id],
            action_type=MutationActionType.NO_OP,
            risk_score=0.0,
        )

    def _build_mutation_failure_decision(
        self,
        *,
        activation_candidate_id: str,
        decision_id: str,
        reason: str,
    ) -> MutationDecision:
        """Build a safe no-op decision for proposer failures."""

        if self.session_id is None:
            raise ValueError(_NO_ACTIVE_SESSION_ERROR)

        return MutationDecision(
            decision_id=decision_id,
            session_id=self.session_id,
            actor_node_id=activation_candidate_id,
            target_ids=[],
            action_type=MutationActionType.NO_OP,
            risk_score=0.0,
            accepted=False,
            rejected_reason=reason,
            safety_checks=[
                SafetyCheckResult(
                    check_name="mutation_proposer_guard",
                    status=CheckStatus.FAIL,
                    message=reason,
                )
            ],
        )

    def _propose_llm_mutation(
        self,
        *,
        activation_candidate_id: str,
        session_state: _RuntimeSessionState,
        now: datetime,
    ) -> tuple[MutationProposal | None, MutationDecision | None]:
        if self.session is None or self.session_id is None:
            return None, None

        if self._is_mutation_proposer_backoff_active(session_state, now):
            decision_id = self._next_mutation_cycle_decision_id()
            failure_message = (
                "mutation proposer backoff active after "
                f"{session_state.mutation_proposer_failure_count} consecutive failures"
            )
            self._append_mutation_lifecycle_event(
                proposal=self._build_mutation_failure_proposal(
                    activation_candidate_id=activation_candidate_id,
                    decision_id=decision_id,
                ),
                event_type=MutationEventKind.FAILED,
                message=failure_message,
            )
            return None, self._build_mutation_failure_decision(
                activation_candidate_id=activation_candidate_id,
                decision_id=decision_id,
                reason=failure_message,
            )

        try:
            narrative_context = self._narrative_context_builder.build(
                self.session,
                self.session_graph,
                activation_candidate_id,
            )
            proposal = self._mutation_proposer.propose(narrative_context)
        except (LLMMutationProposerError, ValueError) as error:
            decision_id = self._next_mutation_cycle_decision_id()
            failure_detail = str(error.__cause__ or error)
            failure_message = f"mutation proposer failed: {failure_detail}"
            self._record_mutation_proposer_failure(session_state, now=now)
            event_message = failure_message
            if session_state.mutation_proposer_backoff_until is not None:
                event_message = (
                    f"{failure_message}; backoff active until "
                    f"{session_state.mutation_proposer_backoff_until.isoformat()}"
                )
            self._append_mutation_lifecycle_event(
                proposal=self._build_mutation_failure_proposal(
                    activation_candidate_id=activation_candidate_id,
                    decision_id=decision_id,
                ),
                event_type=MutationEventKind.FAILED,
                message=event_message,
            )
            return None, self._build_mutation_failure_decision(
                activation_candidate_id=activation_candidate_id,
                decision_id=decision_id,
                reason=failure_message,
            )

        self._reset_mutation_proposer_failure_state(session_state)
        return proposal, None

    def _prune_runtime_guardrails(
        self, session_state: _RuntimeSessionState, now: datetime
    ) -> None:
        """Drop expired cooldown and mutation-burst windows for the active session."""

        guardrail_state = ConsistencyGuardrailState(
            node_cooldowns=dict(session_state.node_cooldowns),
            recent_mutation_times=list(session_state.recent_mutation_times),
            burst_check_pending=session_state.burst_check_pending,
            burst_cooldown_until=session_state.burst_cooldown_until,
        )
        pruned_state = prune_consistency_guardrails(
            guardrail_state,
            now=now,
            mutation_burst_window=self._mutation_burst_window,
            mutation_burst_trigger_count=self._mutation_burst_trigger_count,
        )
        session_state.node_cooldowns = dict(pruned_state.node_cooldowns)
        session_state.recent_mutation_times = list(pruned_state.recent_mutation_times)
        session_state.burst_cooldown_until = pruned_state.burst_cooldown_until
        session_state.burst_check_pending = pruned_state.burst_check_pending

        if (
            session_state.mutation_proposer_backoff_until is not None
            and session_state.mutation_proposer_backoff_until <= now
        ):
            session_state.mutation_proposer_backoff_until = None

    def _is_node_cooling_down(
        self,
        session_state: _RuntimeSessionState,
        node_id: str,
        now: datetime,
    ) -> bool:
        cooldown_until = session_state.node_cooldowns.get(node_id)
        if cooldown_until is None:
            return False

        if now >= cooldown_until:
            del session_state.node_cooldowns[node_id]
            return False

        return True

    def _is_burst_cooldown_active(
        self, session_state: _RuntimeSessionState, now: datetime
    ) -> bool:
        burst_cooldown_until = session_state.burst_cooldown_until
        return burst_cooldown_until is not None and now < burst_cooldown_until

    def _record_runtime_mutation_guardrails(
        self,
        session_state: _RuntimeSessionState,
        *,
        candidate_id: str,
        resolved_at: datetime,
        accepted: bool,
    ) -> None:
        guardrail_state = ConsistencyGuardrailState(
            node_cooldowns=dict(session_state.node_cooldowns),
            recent_mutation_times=list(session_state.recent_mutation_times),
            burst_check_pending=session_state.burst_check_pending,
            burst_cooldown_until=session_state.burst_cooldown_until,
        )
        updated_state = record_consistency_outcome(
            guardrail_state,
            candidate_id=candidate_id,
            resolved_at=resolved_at,
            accepted=accepted,
            mutation_cooldown=self._mutation_cooldown,
            mutation_burst_trigger_count=self._mutation_burst_trigger_count,
            global_mutation_storm_threshold=self._global_mutation_storm_threshold,
        )
        session_state.recent_mutation_times = list(updated_state.recent_mutation_times)
        session_state.burst_check_pending = updated_state.burst_check_pending
        session_state.burst_cooldown_until = updated_state.burst_cooldown_until
        session_state.node_cooldowns = dict(updated_state.node_cooldowns)

    def _maybe_run_global_consistency_check(
        self,
        session_state: _RuntimeSessionState,
        now: datetime,
    ) -> None:
        """Run interval-gated global consistency sampling when due."""

        if self.session is None or self.session_id is None:
            return

        coherence = self.session.coherence
        if coherence is None:
            return

        guardrail_state = ConsistencyGuardrailState(
            node_cooldowns=dict(session_state.node_cooldowns),
            recent_mutation_times=list(session_state.recent_mutation_times),
            burst_check_pending=session_state.burst_check_pending,
            burst_cooldown_until=session_state.burst_cooldown_until,
        )
        if not should_run_global_consistency_check(
            guardrail_state,
            now=now,
            global_consistency_check_interval=self._global_consistency_check_interval,
            last_global_consistency_check_at=coherence.sampled_at,
        ):
            return

        updated_state = mark_global_consistency_check_completed(guardrail_state)
        session_state.burst_check_pending = updated_state.burst_check_pending
        coherence.sampled_at = now
        self._append_runtime_event(
            event_type=EventType.COHERENCE_SAMPLED,
            command_id=f"coherence-sampled-{self._runtime_event_sequence + 1:06d}",
            session_id=self.session_id,
            message="coherence sampled",
        )

    def _require_active_session(self, required_status: SessionStatus) -> None:
        if self.session is None or self.session_id is None:
            raise ValueError(_NO_ACTIVE_SESSION_ERROR)

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
            raise ValueError(_COMMAND_SESSION_MISMATCH_ERROR)

    def _activate_session(self, session_id: UUID) -> None:
        session_state = self._session_states.get(session_id)
        if session_state is None:
            raise ValueError(f"unknown session '{session_id}'")

        self.session_id = session_id
        self.session = session_state.session
        self.session_graph = session_state.session_graph

    def get_active_graph_session(self) -> GraphSession | None:
        """Return the currently active GraphSession from the registry.

        Returns:
            Defensive copy of the active GraphSession, or None if no active graph.
        """
        try:
            return self.graph_registry.get_active_session()
        except NoActiveGraphError:
            return None

    def register_graph_session(self, session: GraphSession) -> GraphSession:
        """Register a GraphSession in the multi-graph registry.

        Args:
            session: The GraphSession to register.

        Returns:
            Defensive copy of the registered session.
        """
        return self.graph_registry.register_session(session)

    def switch_to_next_graph(self) -> GraphSession:
        """Switch to the next graph in cyclic order (Tab navigation).

        Returns:
            Defensive copy of the newly active session.

        Raises:
            NoActiveGraphError: If no graphs are registered.
        """
        start_time = perf_counter()
        previous_graph_id = self._active_graph_id_or_none()
        switched_session = self.graph_registry.switch_to_next()
        self._activate_session(UUID(switched_session.graph_id))
        elapsed_ms = (perf_counter() - start_time) * 1000
        self._record_graph_switch_event(
            direction=GraphNavigationDirection.NEXT,
            previous_graph_id=previous_graph_id,
            active_graph_id=switched_session.graph_id,
            elapsed_ms=elapsed_ms,
        )
        LOGGER.info(
            "graph switch next completed in %.2f ms (%s -> %s)",
            elapsed_ms,
            previous_graph_id or "none",
            switched_session.graph_id,
        )
        return switched_session

    def switch_to_previous_graph(self) -> GraphSession:
        """Switch to the previous graph in cyclic order (Shift+Tab navigation).

        Returns:
            Defensive copy of the newly active session.

        Raises:
            NoActiveGraphError: If no graphs are registered.
        """
        start_time = perf_counter()
        previous_graph_id = self._active_graph_id_or_none()
        switched_session = self.graph_registry.switch_to_previous()
        self._activate_session(UUID(switched_session.graph_id))
        elapsed_ms = (perf_counter() - start_time) * 1000
        self._record_graph_switch_event(
            direction=GraphNavigationDirection.PREVIOUS,
            previous_graph_id=previous_graph_id,
            active_graph_id=switched_session.graph_id,
            elapsed_ms=elapsed_ms,
        )
        LOGGER.info(
            "graph switch previous completed in %.2f ms (%s -> %s)",
            elapsed_ms,
            previous_graph_id or "none",
            switched_session.graph_id,
        )
        return switched_session

    def remove_graph_session(self, graph_id: str) -> None:
        """Remove a graph session and preserve valid active-graph context."""

        self.graph_registry.remove_session(graph_id)
        remaining = self.graph_registry.get_session_count()
        LOGGER.info(
            "removed graph session %s (remaining_graphs=%d)",
            graph_id,
            remaining,
        )

    def get_multi_graph_status_snapshot(self) -> MultiGraphStatusSnapshot:
        """Get a status snapshot for TUI multi-graph rendering.

        Returns:
            MultiGraphStatusSnapshot with active position, total graphs,
            and active running state. Returns idle state when no graphs exist.
        """
        total = self.graph_registry.get_session_count()
        if total == 0:
            return MultiGraphStatusSnapshot(
                active_position=1,
                total_graphs=0,
                active_running_state=RunningState.IDLE,
            )

        try:
            active_session = self.graph_registry.get_active_session()
            active_index = self.graph_registry.get_active_index()
            return MultiGraphStatusSnapshot(
                active_position=active_index + 1,  # 1-based for display
                total_graphs=total,
                active_running_state=RunningState(
                    active_session.execution_status.value
                ),
            )
        except NoActiveGraphError:
            return MultiGraphStatusSnapshot(
                active_position=1,
                total_graphs=total,
                active_running_state=RunningState.IDLE,
            )

    def create_fork_request(
        self, seed: str | None = None
    ) -> ForkFromCurrentNodeRequest | None:
        """Create a ForkFromCurrentNodeRequest from the active graph context.

        Args:
            seed: Optional user-provided seed value.

        Returns:
            ForkFromCurrentNodeRequest if active graph exists with current node,
            None otherwise.
        """
        try:
            active_session = self.graph_registry.get_active_session()
        except NoActiveGraphError:
            return None

        if active_session.current_node_id is None:
            return None

        return ForkFromCurrentNodeRequest(
            active_graph_id=active_session.graph_id,
            current_node_id=active_session.current_node_id,
            seed=seed,
        )

    def create_graph_switch_request(
        self, direction: GraphNavigationDirection
    ) -> GraphSwitchRequest | None:
        """Create a GraphSwitchRequest for navigation.

        Args:
            direction: Navigation direction (NEXT or PREVIOUS).

        Returns:
            GraphSwitchRequest if there are multiple graphs to switch between,
            None if there's only one or zero graphs.
        """
        total = self.graph_registry.get_session_count()
        if total < 2:
            return None

        try:
            sessions = self.graph_registry.list_sessions()
            active_index = self.graph_registry.get_active_index()
        except NoActiveGraphError:
            return None

        # Calculate target index based on direction
        if direction == GraphNavigationDirection.NEXT:
            target_index = (active_index + 1) % total
        else:
            target_index = (active_index - 1) % total

        target_session = sessions[target_index]

        return GraphSwitchRequest(
            target_graph_id=target_session.graph_id,
            direction=direction,
            preserve_current=True,
        )

    def update_current_node_id(self, node_id: str) -> bool:
        """Update the current_node_id for the active graph session.

        Args:
            node_id: The new current node ID.

        Returns:
            True if update succeeded, False if no active graph.
        """
        try:
            active_session = self.graph_registry.get_active_session()
        except NoActiveGraphError:
            return False

        updated_session = active_session.model_copy(
            update={"current_node_id": node_id, "last_activity_at": utc_now()}
        )
        self.graph_registry.update_session(updated_session)
        return True

    def update_execution_status(self, status: ExecutionStatus) -> bool:
        """Update the execution_status for the active graph session.

        Args:
            status: The new execution status.

        Returns:
            True if update succeeded, False if no active graph.
        """
        try:
            active_session = self.graph_registry.get_active_session()
        except NoActiveGraphError:
            return False

        updated_session = active_session.model_copy(
            update={"execution_status": status, "last_activity_at": utc_now()}
        )
        self.graph_registry.update_session(updated_session)
        return True

    @property
    def graph_count(self) -> int:
        """Return the number of registered graph sessions."""
        return self.graph_registry.get_session_count()

    @property
    def active_graph_index(self) -> int:
        """Return the current active graph index (0-based)."""
        return self.graph_registry.get_active_index()

    def fork_from_current_node(
        self,
        fork_request: "ForkFromCurrentNodeRequest",
    ) -> "GraphSession | None":
        """Create a fork from the current node and set it as active.

        Args:
            fork_request: The validated fork request containing active_graph_id,
                        current_node_id, and optional seed.

        Returns:
            The newly created GraphSession if successful, None otherwise.
        """

        start_time = perf_counter()

        try:
            # Verify source session exists
            self.graph_registry.get_session(fork_request.active_graph_id)
        except Exception as error:
            LOGGER.warning("Failed to get source session for fork: %s", error)
            return None

        # Generate new graph ID (keep as UUID for session state key)
        forked_session_id = uuid4()
        forked_graph_id = str(forked_session_id)
        now = utc_now()

        # Create the forked session
        forked_session = GraphSession(
            graph_id=forked_graph_id,
            current_node_id=fork_request.current_node_id,
            execution_status=ExecutionStatus.RUNNING,
            is_active=False,  # Will be set active after registration
            last_activity_at=now,
        )

        # Register the new session (appends to registry) - T024
        self.graph_registry.register_session(forked_session)

        # Also add to _session_states so switching works properly
        forked_graph = copy.deepcopy(self.session_graph)
        self._retarget_graph_session_ids(forked_graph, forked_session_id)
        _mark_runtime_mutation_graph(forked_graph)
        _reset_runtime_mutation_cycle(forked_graph)
        # Create required telemetry for running session
        forked_coherence = CoherenceSnapshot(
            global_score=0.5,
            local_scores=[],
            global_check_status=CheckStatus.PASS,
            sampled_at=now,
            checked_by="fork_from_current_node",
        )
        forked_budget = BudgetTelemetry(
            estimated_cost_usd=Decimal("0.0"),
            budget_limit_usd=Decimal("5.00"),
            token_input_count=0,
            token_output_count=0,
            model_call_count=0,
        )
        forked_termination = TerminationVoteState(
            active_node_count=1,
            votes_for_termination=0,
            votes_against_termination=0,
            majority_threshold=0.51,
            termination_reached=False,
            last_updated_at=now,
        )

        self._session_states[forked_session_id] = _RuntimeSessionState(
            session=Session(
                session_id=forked_session_id,
                status=SessionStatus.RUNNING,
                seed_text=fork_request.seed or "",
                graph_version=0,
                active_node_ids=[fork_request.current_node_id]
                if fork_request.current_node_id
                else [],
                created_at=now,
                updated_at=now,
                parent_session_id=UUID(fork_request.active_graph_id)
                if fork_request.active_graph_id
                else None,
                coherence=forked_coherence,
                budget=forked_budget,
                termination=forked_termination,
            ),
            session_graph=forked_graph,
            event_log=EventLog(
                session_id=forked_session_id, latest_sequence=0, events=[]
            ),
        )

        # Set the forked session as active - T025
        active_session = self.graph_registry.set_active_session(forked_graph_id)

        # Calculate timing
        elapsed_ms = (perf_counter() - start_time) * 1000

        # Log the fork operation - T028, T056
        # Use the parent graph ID as session_id if no active session exists
        event_session_id = self.session_id or UUID(fork_request.active_graph_id)
        self._append_runtime_event(
            event_type=_RuntimeEventType.FORK_SESSION,
            command_id=f"fork-from-node-{forked_graph_id[:8]}",
            session_id=event_session_id,
            message=f"Fork created from node {fork_request.current_node_id} with seed {fork_request.seed!r} [{elapsed_ms:.2f}ms]",
            forked_session_id=UUID(forked_graph_id),
            parent_session_id=UUID(fork_request.active_graph_id),
        )

        LOGGER.info(
            "Forked graph %s from %s at node %s in %.2f ms",
            forked_graph_id,
            fork_request.active_graph_id,
            fork_request.current_node_id,
            elapsed_ms,
        )

        return active_session

    def _append_runtime_event(
        self,
        *,
        event_type: _RuntimeEventType | MutationEventKind | EventType,
        command_id: str,
        session_id: UUID | None,
        message: str,
        edge_id: str | None = None,
        forked_session_id: UUID | None = None,
        parent_session_id: UUID | None = None,
    ) -> None:
        if session_id is None:
            raise ValueError(_NO_ACTIVE_SESSION_ERROR)

        self._runtime_event_sequence += 1
        runtime_event = _RuntimeEvent(
            sequence=self._runtime_event_sequence,
            event_type=event_type,
            session_id=session_id,
            occurred_at=utc_now(),
            command_id=command_id,
            message=message,
            edge_id=edge_id,
            forked_session_id=forked_session_id,
            parent_session_id=parent_session_id,
        )
        self._runtime_event_buffer.append(runtime_event)
        self._mirror_runtime_event_to_event_log(runtime_event)

    def _active_graph_id_or_none(self) -> str | None:
        """Return the active graph identifier when one exists."""

        try:
            return self.graph_registry.get_active_session().graph_id
        except NoActiveGraphError:
            return None

    def _record_graph_switch_event(
        self,
        *,
        direction: GraphNavigationDirection,
        previous_graph_id: str | None,
        active_graph_id: str,
        elapsed_ms: float = 0.0,
    ) -> None:
        """Emit structured logs/events for graph switch operations."""

        status = self.get_multi_graph_status_snapshot()
        message = (
            f"graph switch {direction.value}: "
            f"{previous_graph_id or 'none'} -> {active_graph_id} "
            f"({status.active_position}/{status.total_graphs}) "
            f"[{elapsed_ms:.2f}ms]"
        )
        LOGGER.info(message)

        event_session_id = self.session_id
        if event_session_id is None:
            event_session_id = UUID(active_graph_id)

        self._append_runtime_event(
            event_type=_RuntimeEventType.GRAPH_SWITCH,
            command_id=f"graph-switch-{direction.value}-{active_graph_id[:8]}",
            session_id=event_session_id,
            message=message,
        )

    def _append_mutation_lifecycle_event(
        self,
        *,
        proposal: MutationProposal,
        event_type: MutationEventKind,
        message: str,
    ) -> None:
        """Append a typed mutation lifecycle event with the proposal metadata."""

        self._append_runtime_event(
            event_type=event_type,
            command_id=proposal.decision_id,
            session_id=self.session_id,
            edge_id=proposal.target_ids[0] if proposal.target_ids else None,
            message=message,
        )
        LOGGER.info(
            "mutation decision telemetry event=%s decision=%s session=%s detail=%s",
            event_type.value,
            proposal.decision_id,
            self.session_id,
            message,
        )

    def _append_session_event(
        self,
        *,
        session_id: UUID,
        event_type: EventType,
        command_id: str,
        message: str,
        target_ids: list[str] | None = None,
        actor_id: str | None = None,
        mutation_id: str | None = None,
        outcome: EventOutcome | None = None,
    ) -> None:
        session_state = self._session_states.get(session_id)
        if session_state is None:
            return

        event_log = session_state.event_log
        event_id = f"{command_id}-{event_log.next_sequence:06d}"
        sequence = event_log.next_sequence
        occurred_at = utc_now()
        event_targets = list(target_ids or [])
        if mutation_id is None and outcome is None:
            event_log.append(
                SessionEvent(
                    event_id=event_id,
                    sequence=sequence,
                    session_id=session_id,
                    event_type=event_type,
                    occurred_at=occurred_at,
                    actor_id=actor_id,
                    target_ids=event_targets,
                    message=message,
                )
            )
            return

        event_log.append(
            MutationStreamEvent(
                event_id=event_id,
                sequence=sequence,
                session_id=session_id,
                event_type=event_type,
                occurred_at=occurred_at,
                actor_id=actor_id,
                target_ids=event_targets,
                message=message,
                mutation_id=mutation_id,
                outcome=outcome,
            )
        )

    def _mirror_runtime_event_to_event_log(self, runtime_event: _RuntimeEvent) -> None:
        session_state = self._session_states.get(runtime_event.session_id)
        if session_state is None:
            return

        event_type, outcome = self._map_runtime_event_to_event_type(
            runtime_event.event_type
        )
        if event_type is None:
            return

        target_ids = [runtime_event.edge_id] if runtime_event.edge_id else []
        mutation_id = runtime_event.command_id if outcome is not None else None
        self._append_session_event(
            session_id=runtime_event.session_id,
            event_type=event_type,
            command_id=runtime_event.command_id,
            message=runtime_event.message,
            target_ids=target_ids,
            actor_id=runtime_event.command_id,
            mutation_id=mutation_id,
            outcome=outcome,
        )

    def _map_runtime_event_to_event_type(
        self, event_type: _RuntimeEventType | MutationEventKind | EventType
    ) -> tuple[EventType | None, EventOutcome | None]:
        if isinstance(event_type, EventType):
            return event_type, None

        if event_type is _RuntimeEventType.LOCK_EDGE:
            return EventType.EDGE_LOCKED, None

        if event_type is _RuntimeEventType.UNLOCK_EDGE:
            return EventType.EDGE_UNLOCKED, None

        if event_type is _RuntimeEventType.FORK_SESSION:
            return EventType.SESSION_RESUMED, None

        if event_type is _RuntimeEventType.GRAPH_SWITCH:
            return EventType.SESSION_RESUMED, None

        if event_type is MutationEventKind.PROPOSED:
            return EventType.MUTATION_PROPOSED, None

        if event_type is MutationEventKind.APPLIED:
            return EventType.MUTATION_APPLIED, EventOutcome.SUCCESS

        if event_type is MutationEventKind.REJECTED:
            return EventType.MUTATION_REJECTED, EventOutcome.BLOCKED

        if event_type is MutationEventKind.VETOED:
            return EventType.MUTATION_REJECTED, EventOutcome.BLOCKED

        if event_type is MutationEventKind.COOLED_DOWN:
            return EventType.MUTATION_REJECTED, EventOutcome.WARN

        if event_type is MutationEventKind.FAILED:
            return EventType.ERROR_REPORTED, EventOutcome.FAIL

        return None, None

    def _emit_budget_telemetry_events(self) -> None:
        if (
            self.session is None
            or self.session.budget is None
            or self.session_id is None
        ):
            return

        budget = self.session.budget
        estimated_cost = budget.estimated_cost_usd
        budget_limit = budget.budget_limit_usd
        warning_threshold = budget_limit * _RUNTIME_BUDGET_WARNING_RATIO

        if not budget.soft_warning_emitted and estimated_cost >= warning_threshold:
            budget.soft_warning_emitted = True
            self._append_runtime_event(
                event_type=EventType.BUDGET_WARNING,
                command_id=f"budget-warning-{self._runtime_event_sequence + 1:06d}",
                session_id=self.session_id,
                message=(
                    "budget warning: "
                    f"estimated_cost_usd={estimated_cost} "
                    f"budget_limit_usd={budget_limit}"
                ),
            )

        if not budget.hard_breach_emitted and estimated_cost >= budget_limit:
            budget.hard_breach_emitted = True
            self._append_runtime_event(
                event_type=EventType.BUDGET_BREACH,
                command_id=f"budget-breach-{self._runtime_event_sequence + 1:06d}",
                session_id=self.session_id,
                message=(
                    "budget breach: "
                    f"estimated_cost_usd={estimated_cost} "
                    f"budget_limit_usd={budget_limit}"
                ),
            )

    def _require_inspectable_node(self, node_id: str) -> None:
        if self.session is None or self.session_id is None:
            raise ValueError(_NO_ACTIVE_SESSION_ERROR)

        graph_node = get_graph_node(self.session_graph, node_id)
        scene_node = get_scene_node(self.session_graph, node_id)
        if graph_node is None or scene_node is None:
            raise ValueError(
                f"node '{node_id}' does not exist or is missing inspection metadata"
            )

        if (
            graph_node.session_id != self.session_id
            or scene_node.session_id != self.session_id
        ):
            raise ValueError(f"node '{node_id}' does not belong to the active session")

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
