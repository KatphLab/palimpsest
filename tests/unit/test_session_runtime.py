"""Tests for the session runtime command router skeleton."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from agents.llm_mutation_proposer import LLMMutationProposer
from graph.session_graph import SessionGraph
from models.commands import (
    CommandResult,
    CommandType,
    StartSessionCommand,
    StartSessionPayload,
)
from models.common import (
    CheckStatus,
    MutationActionType,
    MutationEventKind,
    SafetyCheckResult,
)
from models.events import EventType
from runtime.session_runtime import SessionRuntime, _RuntimeEventType
from tests.fixtures import (
    DeterministicSceneGenerationProvider,
    SequencedMutationProposalProvider,
    build_mutation_response,
)
from utils.time import utc_now


def _build_runtime(
    proposal_provider: SequencedMutationProposalProvider,
) -> SessionRuntime:
    """Build a runtime with deterministic scene and proposal providers."""

    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        mutation_proposer=LLMMutationProposer(provider=proposal_provider),
    )
    runtime._scene_agent._provider = DeterministicSceneGenerationProvider()
    return runtime


def test_session_runtime_owns_the_session_graph_instance() -> None:
    """The runtime should own the graph service it was given."""

    graph = SessionGraph()

    runtime = SessionRuntime(session_graph=graph)

    assert runtime.session_graph is graph


def test_session_runtime_routes_start_commands_to_the_start_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The router should dispatch a start command to the matching handler."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    command = StartSessionCommand(
        command_id="cmd-001",
        command_type=CommandType.START_SESSION,
        payload=StartSessionPayload(seed_text="seed text"),
    )
    expected = CommandResult(
        command_id=command.command_id,
        accepted=True,
        session_id=UUID(int=1),
        state_version=0,
        message="handled",
    )

    def fake_start_handler(incoming_command: StartSessionCommand) -> CommandResult:
        assert incoming_command is command
        return expected

    monkeypatch.setattr(runtime, "_handle_start_session", fake_start_handler)

    result = runtime.handle_command(command)

    assert result is expected


def test_session_runtime_discards_old_runtime_events_after_the_buffer_limit() -> None:
    """The runtime should keep only the most recent 1000 events."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    runtime.session_id = UUID(int=1)

    for index in range(1001):
        runtime._append_runtime_event(
            event_type=_RuntimeEventType.LOCK_EDGE,
            command_id=f"cmd-{index:04d}",
            session_id=runtime.session_id,
            message="event",
        )

    events = runtime.runtime_event_buffer

    assert len(events) == 1000
    assert events[0].sequence == 2
    assert events[-1].sequence == 1001


def test_session_runtime_exposes_all_runtime_event_kinds() -> None:
    """The runtime event enum should cover all supported command kinds."""

    assert {member.value for member in _RuntimeEventType} == {
        "add_node",
        "add_edge",
        "remove_edge",
        "rewrite_node",
        "prune_branch",
        "lock_edge",
        "unlock_edge",
        "fork_session",
        "graph_switch",
    }


def test_runtime_uses_the_llm_proposed_mutation_when_proposal_succeeds() -> None:
    """Runtime should apply the LLM-proposed mutation when proposal succeeds."""

    proposal_provider = SequencedMutationProposalProvider(
        [
            lambda prompt: build_mutation_response(
                prompt,
                decision_id="mutation-cycle-001",
                action_type=MutationActionType.ADD_NODE,
            )
        ]
    )
    runtime = _build_runtime(proposal_provider)
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-llm-success-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A lantern glows in the storm."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    before_nodes = runtime.session_graph.graph.number_of_nodes()

    decision = runtime.run_mutation_cycle()

    assert decision is not None
    assert decision.accepted is True
    assert decision.action_type is MutationActionType.ADD_NODE
    assert runtime.session_graph.graph.number_of_nodes() > before_nodes
    assert len(proposal_provider.prompts) == 1


def test_runtime_records_llm_proposer_failure_without_applying_mutation() -> None:
    """Runtime should return a safe no-op result when proposal generation fails."""

    proposal_provider = SequencedMutationProposalProvider(
        [RuntimeError("provider unavailable")]
    )
    runtime = _build_runtime(proposal_provider)
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-failure-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass gate hums with static."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    before_nodes = runtime.session_graph.graph.number_of_nodes()

    decision = runtime.run_mutation_cycle()

    assert decision is not None
    assert decision.action_type is MutationActionType.NO_OP
    assert decision.accepted is False
    assert decision.rejected_reason == "mutation proposer failed: provider unavailable"
    assert decision.safety_checks == [
        SafetyCheckResult(
            check_name="mutation_proposer_guard",
            status=CheckStatus.FAIL,
            message="mutation proposer failed: provider unavailable",
        )
    ]
    assert runtime.session_graph.graph.number_of_nodes() == before_nodes

    session_id = runtime.session_id
    assert session_id is not None
    session_state = runtime._session_states[session_id]
    assert session_state.mutation_proposer_failure_count == 1
    assert session_state.mutation_proposer_backoff_until is None
    assert runtime.runtime_event_buffer[-1].event_type is MutationEventKind.FAILED
    assert "provider unavailable" in runtime.runtime_event_buffer[-1].message


def test_runtime_enters_llm_proposer_backoff_after_consecutive_failures() -> None:
    """Repeated failures should trigger proposer backoff and skip LLM calls."""

    proposal_provider = SequencedMutationProposalProvider(
        [
            RuntimeError("provider unavailable"),
            RuntimeError("provider unavailable again"),
        ]
    )
    runtime = _build_runtime(proposal_provider)
    runtime._mutation_proposer_failure_threshold = 2
    runtime._mutation_proposer_backoff_duration = timedelta(minutes=5)
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-backoff-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass gate hums with static."),
        )
    )

    assert start_result.accepted is True

    first_decision = runtime.run_mutation_cycle()
    second_decision = runtime.run_mutation_cycle()
    third_decision = runtime.run_mutation_cycle()

    assert first_decision is not None
    assert second_decision is not None
    assert third_decision is not None
    assert first_decision.action_type is MutationActionType.NO_OP
    assert second_decision.action_type is MutationActionType.NO_OP
    assert third_decision.action_type is MutationActionType.NO_OP
    assert third_decision.rejected_reason == (
        "mutation proposer backoff active after 2 consecutive failures"
    )
    assert len(proposal_provider.prompts) == 2

    session_id = runtime.session_id
    assert session_id is not None
    session_state = runtime._session_states[session_id]
    assert session_state.mutation_proposer_failure_count == 2
    assert session_state.mutation_proposer_backoff_until is not None
    assert runtime.runtime_event_buffer[-1].event_type is MutationEventKind.FAILED
    assert "backoff" in runtime.runtime_event_buffer[-1].message


def test_runtime_resets_llm_proposer_failure_state_after_success() -> None:
    """A successful proposer call should clear failure and backoff state."""

    proposal_provider = SequencedMutationProposalProvider(
        [
            RuntimeError("provider unavailable"),
            lambda prompt: build_mutation_response(
                prompt,
                decision_id="mutation-cycle-002",
                action_type=MutationActionType.ADD_NODE,
            ),
            RuntimeError("provider unavailable again"),
        ]
    )
    runtime = _build_runtime(proposal_provider)
    runtime._mutation_proposer_failure_threshold = 2
    runtime._mutation_proposer_backoff_duration = timedelta(minutes=5)
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-reset-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass gate hums with static."),
        )
    )

    assert start_result.accepted is True

    first_decision = runtime.run_mutation_cycle()
    second_decision = runtime.run_mutation_cycle()
    third_decision = runtime.run_mutation_cycle()

    assert first_decision is not None
    assert second_decision is not None
    assert third_decision is not None
    assert first_decision.action_type is MutationActionType.NO_OP
    assert second_decision.accepted is True
    assert second_decision.action_type is MutationActionType.ADD_NODE
    assert third_decision.action_type is MutationActionType.NO_OP
    assert len(proposal_provider.prompts) == 3

    session_id = runtime.session_id
    assert session_id is not None
    session_state = runtime._session_states[session_id]
    assert session_state.mutation_proposer_failure_count == 1
    assert session_state.mutation_proposer_backoff_until is None
    assert runtime.runtime_event_buffer[-1].event_type is MutationEventKind.FAILED


def test_runtime_records_mutation_skip_event_when_no_candidate_exists() -> None:
    """Runtime should emit a lifecycle event when no candidate can be selected."""

    runtime = SessionRuntime(session_graph=SessionGraph())
    runtime._scene_agent._provider = DeterministicSceneGenerationProvider()
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-skip-event-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass gate hums with static."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    runtime.session.active_node_ids = []
    runtime.session_graph.graph.clear()
    before_count = len(runtime.runtime_event_buffer)

    decision = runtime.run_mutation_cycle()

    assert decision is None
    events = runtime.runtime_event_buffer
    assert len(events) == before_count + 1
    assert events[-1].message == "mutation skipped: no activation candidate"


def test_runtime_emits_global_consistency_event_when_interval_elapsed() -> None:
    """Runtime should emit coherence sampling when interval gating is due."""

    runtime = _build_runtime(SequencedMutationProposalProvider([]))
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-consistency-interval-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass gate hums with static."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    session_id = runtime.session_id
    assert session_id is not None
    runtime._global_consistency_check_interval = timedelta(seconds=60)
    assert runtime.session.coherence is not None
    runtime.session.coherence.sampled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runtime.session.active_node_ids = []
    runtime.session_graph.graph.clear()

    decision = runtime.run_mutation_cycle()

    assert decision is None
    events = runtime.runtime_event_buffer
    assert events[-2].event_type is EventType.COHERENCE_SAMPLED
    assert events[-1].message == "mutation skipped: no activation candidate"
    assert runtime.session.coherence is not None
    assert runtime.session.coherence.sampled_at > datetime(
        2026, 1, 1, tzinfo=timezone.utc
    )


def test_runtime_emits_global_consistency_event_when_burst_pending() -> None:
    """Burst-triggered checks should run immediately and clear pending state."""

    runtime = _build_runtime(SequencedMutationProposalProvider([]))
    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-consistency-burst-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A brass gate hums with static."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None
    session_id = runtime.session_id
    assert session_id is not None
    now = utc_now()
    runtime._global_consistency_check_interval = timedelta(days=1)
    runtime._mutation_burst_trigger_count = 1
    runtime._mutation_burst_window = timedelta(minutes=5)
    assert runtime.session.coherence is not None
    runtime.session.coherence.sampled_at = now
    runtime.session.active_node_ids = []
    runtime.session_graph.graph.clear()
    runtime._session_states[session_id].recent_mutation_times = [now]
    runtime._session_states[session_id].burst_check_pending = True

    decision = runtime.run_mutation_cycle()

    assert decision is None
    events = runtime.runtime_event_buffer
    assert events[-2].event_type is EventType.COHERENCE_SAMPLED
    assert events[-1].message == "mutation skipped: no activation candidate"
    assert runtime._session_states[session_id].burst_check_pending is False
