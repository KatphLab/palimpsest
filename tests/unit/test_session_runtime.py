"""Tests for the session runtime command router skeleton."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from typing import cast
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
from models.session import SceneGenerationProvider
from runtime.session_runtime import SessionRuntime, _RuntimeEventType


class DeterministicSceneGenerationProvider(SceneGenerationProvider):
    """Deterministic scene text provider for runtime unit tests."""

    def generate_first_scene(self, *, seed_text: str) -> str:
        return f"FIRST SCENE :: {seed_text}"


class SequencedMutationProposalProvider:
    """Deterministic LLM proposal provider for runtime tests."""

    def __init__(self, responses: list[Callable[[str], str] | Exception]) -> None:
        self._responses = responses
        self.prompts: list[str] = []

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        index = len(self.prompts)
        if index >= len(self._responses):
            raise AssertionError("LLM proposer should not be called during backoff")

        self.prompts.append(prompt)
        response = self._responses[index]
        if isinstance(response, Exception):
            raise response

        return response(prompt)


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


def _narrative_context(prompt: str) -> dict[str, object]:
    """Extract the serialized narrative context from a proposer prompt."""

    context_text = prompt.rsplit("NarrativeContext: ", 1)[1]
    return cast(dict[str, object], json.loads(context_text))


def _mutation_response(
    prompt: str,
    *,
    decision_id: str,
    action_type: MutationActionType,
) -> str:
    """Build a structured mutation proposal response from live context."""

    context = _narrative_context(prompt)
    session_id = UUID(str(context["session_id"]))
    previous_scene_node_id = str(context["previous_scene_node_id"])
    current_scene_node_id = str(context["current_scene_node_id"])

    if action_type is MutationActionType.ADD_NODE:
        target_ids = [current_scene_node_id]
    elif action_type is MutationActionType.REMOVE_EDGE:
        target_ids = [f"{previous_scene_node_id}->{current_scene_node_id}"]
    else:
        raise AssertionError(f"unsupported test action {action_type}")

    return json.dumps(
        {
            "decision_id": decision_id,
            "session_id": str(session_id),
            "actor_node_id": current_scene_node_id,
            "target_ids": target_ids,
            "action_type": action_type.value,
            "risk_score": 0.25,
        }
    )


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
    }


def test_runtime_uses_the_llm_proposed_mutation_when_proposal_succeeds() -> None:
    """Runtime should apply the LLM-proposed mutation when proposal succeeds."""

    proposal_provider = SequencedMutationProposalProvider(
        [
            lambda prompt: _mutation_response(
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
            lambda prompt: _mutation_response(
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
