"""Session runtime command router with owned graph state."""

from __future__ import annotations

import copy
import logging
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from threading import Lock
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field

from agents.llm_mutation_proposer import LLMMutationProposer, LLMMutationProposerError
from agents.mutation_agent import MutationAgent
from agents.mutation_engine import MutationEngine
from agents.narrative_context_builder import NarrativeContextBuilder
from agents.scene_agent import SceneAgent
from config.env import (
    _DEFAULT_GLOBAL_MUTATION_STORM_THRESHOLD,
    _DEFAULT_MUTATION_BURST_TRIGGER_COUNT,
    _DEFAULT_MUTATION_BURST_WINDOW_SECONDS,
    _DEFAULT_SESSION_MUTATION_COOLDOWN_MS,
)
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
from models.common import (
    CheckStatus,
    DriftCategory,
    EventOutcome,
    MutationActionType,
    MutationEventKind,
    ProtectionReason,
    SafetyCheckResult,
    SessionStatus,
    StrictBaseModel,
    UTCDateTime,
)
from models.events import EventType, MutationStreamEvent, SessionEvent
from models.graph import GraphEdge, GraphNode
from models.mutation import MutationDecision, MutationProposal
from models.node import SceneNode
from models.session import Session
from runtime.event_log import EventLog
from runtime.exporter import build_export_artifact, write_export_artifact

__all__ = ["SessionRuntime"]

LOGGER = logging.getLogger(__name__)

_MAX_RUNTIME_EVENTS = 1000
_NO_ACTIVE_SESSION_ERROR = "no active session exists"
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


class SessionRuntime:
    """Own the mutable session graph and route commands into handlers."""

    def __init__(
        self,
        session_graph: SessionGraph | None = None,
        *,
        scene_agent: SceneAgent | None = None,
        mutation_proposer: LLMMutationProposer | None = None,
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
            self.state_version = 1

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
            if self.session is None or self.session_id is None:
                raise ValueError(_NO_ACTIVE_SESSION_ERROR)

            self._require_command_session_matches_active(command.session_id)
            self._require_inspectable_node(command.payload.node_id)
            assert self.session is not None

            node_data = self.session_graph.graph.nodes[command.payload.node_id]
            graph_node = node_data.get("node")
            scene_node = node_data.get("scene_node")
            assert isinstance(graph_node, GraphNode)
            assert isinstance(scene_node, SceneNode)

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
            if self.session is None or self.session_id is None:
                raise ValueError(_NO_ACTIVE_SESSION_ERROR)

            self._require_command_session_matches_active(command.session_id)
            assert self.session is not None
            assert self.session_id is not None

            now = datetime.now(timezone.utc)
            session_snapshot = self.session.snapshot(captured_at=now)
            session_state = self._session_states[self.session_id]
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
            return self._run_mutation_cycle_locked()

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
                refreshed_at=datetime.now(timezone.utc),
            )
            return self._run_mutation_cycle_locked()

    def _build_result(self, command_id: str, message: str) -> CommandResult:
        return CommandResult(
            command_id=command_id,
            accepted=True,
            session_id=self.session_id,
            state_version=self.state_version,
            message=message,
        )

    def _run_mutation_cycle_locked(self) -> MutationDecision | None:
        if self.session is None or self.session_id is None:
            return None

        if self.session.status != SessionStatus.RUNNING:
            return None

        session_state = self._session_states.get(self.session_id)
        if session_state is None:
            return None

        now = datetime.now(timezone.utc)
        self._prune_runtime_guardrails(session_state, now)
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
            activated_at=datetime.now(timezone.utc),
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

        node_cooldown_expiries = {
            node_id: expires_at
            for node_id, expires_at in session_state.node_cooldowns.items()
            if expires_at > now
        }
        session_state.node_cooldowns = node_cooldown_expiries

        burst_window_start = now - self._mutation_burst_window
        session_state.recent_mutation_times = [
            mutated_at
            for mutated_at in session_state.recent_mutation_times
            if mutated_at >= burst_window_start
        ]

        if (
            session_state.burst_cooldown_until is not None
            and session_state.burst_cooldown_until <= now
        ):
            session_state.burst_cooldown_until = None

        if (
            session_state.mutation_proposer_backoff_until is not None
            and session_state.mutation_proposer_backoff_until <= now
        ):
            session_state.mutation_proposer_backoff_until = None

        session_state.burst_check_pending = (
            len(session_state.recent_mutation_times)
            >= self._mutation_burst_trigger_count
        )

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
        session_state.recent_mutation_times.append(resolved_at)
        session_state.burst_check_pending = (
            len(session_state.recent_mutation_times)
            >= self._mutation_burst_trigger_count
        )

        if (
            len(session_state.recent_mutation_times)
            >= self._global_mutation_storm_threshold
        ):
            proposed_cooldown_until = resolved_at + self._mutation_cooldown
            if (
                session_state.burst_cooldown_until is None
                or proposed_cooldown_until > session_state.burst_cooldown_until
            ):
                session_state.burst_cooldown_until = proposed_cooldown_until

        if accepted:
            session_state.node_cooldowns[candidate_id] = (
                resolved_at + self._mutation_cooldown
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
            occurred_at=datetime.now(timezone.utc),
            command_id=command_id,
            message=message,
            edge_id=edge_id,
            forked_session_id=forked_session_id,
            parent_session_id=parent_session_id,
        )
        self._runtime_event_buffer.append(runtime_event)
        self._mirror_runtime_event_to_event_log(runtime_event)

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
        occurred_at = datetime.now(timezone.utc)
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

        if not self.session_graph.graph.has_node(node_id):
            raise ValueError(f"node '{node_id}' does not exist")

        node_data = self.session_graph.graph.nodes[node_id]
        if not isinstance(node_data, dict):
            raise ValueError(f"node '{node_id}' does not exist")

        graph_node = node_data.get("node")
        scene_node = node_data.get("scene_node")
        if not isinstance(graph_node, GraphNode) or not isinstance(
            scene_node, SceneNode
        ):
            raise ValueError(f"node '{node_id}' is missing inspection metadata")

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
