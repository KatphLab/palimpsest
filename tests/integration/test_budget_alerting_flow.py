"""Integration tests for budget warning and breach alert flows."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

import pytest

from agents.llm_mutation_proposer import LLMMutationProposer
from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.common import BudgetTelemetry
from models.events import EventType
from runtime.session_runtime import SessionRuntime
from tests.fixtures import (
    DeterministicSceneGenerationProvider,
    SequencedMutationProposalProvider,
    build_mutation_response,
)

pytestmark = pytest.mark.integration


class _RuntimeEventRecord(Protocol):
    @property
    def event_type(self) -> object: ...


def _build_runtime() -> SessionRuntime:
    """Build a runtime with deterministic scene and mutation providers."""

    mutation_provider = SequencedMutationProposalProvider(
        [
            lambda prompt: build_mutation_response(
                prompt,
                decision_id="mutation-cycle-001",
            ),
            lambda prompt: build_mutation_response(
                prompt,
                decision_id="mutation-cycle-002",
            ),
        ]
    )
    return SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
        mutation_proposer=LLMMutationProposer(provider=mutation_provider),
    )


def _start_running_session(runtime: SessionRuntime) -> None:
    """Start a live session with deterministic scene bootstrapping."""

    result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-budget-alerts-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(
                seed_text="A ledger of costs glows brighter with every cycle."
            ),
        )
    )

    assert result.accepted is True
    assert runtime.session is not None


def _set_budget(runtime: SessionRuntime, *, estimated_cost_usd: str) -> None:
    """Update the active session budget for the next cycle."""

    assert runtime.session is not None
    runtime.session.budget = BudgetTelemetry(
        estimated_cost_usd=Decimal(estimated_cost_usd),
        budget_limit_usd=Decimal("5.00"),
        token_input_count=1200,
        token_output_count=300,
        model_call_count=1,
        soft_warning_emitted=False,
        hard_breach_emitted=False,
    )


def _first_event_index(
    events: tuple[_RuntimeEventRecord, ...], event_type: EventType
) -> int:
    """Return the first index for a matching event type."""

    for index, event in enumerate(events):
        if event.event_type is event_type:
            return index

    raise AssertionError(f"missing {event_type.value} event")


def test_budget_alerts_append_warning_before_breach_and_keep_prior_events_visible() -> (
    None
):
    """Budget alerts should surface warning then breach without losing prior events."""

    runtime = _build_runtime()
    _start_running_session(runtime)

    _set_budget(runtime, estimated_cost_usd="4.25")
    runtime.advance_session_cycle()
    warning_snapshot = runtime.runtime_event_buffer

    warning_index = _first_event_index(warning_snapshot, EventType.BUDGET_WARNING)
    assert warning_snapshot[warning_index].sequence >= 1

    _set_budget(runtime, estimated_cost_usd="5.25")
    runtime.advance_session_cycle()
    breach_snapshot = runtime.runtime_event_buffer

    assert breach_snapshot[: len(warning_snapshot)] == warning_snapshot
    assert (
        _first_event_index(breach_snapshot, EventType.BUDGET_WARNING) == warning_index
    )
    breach_index = _first_event_index(breach_snapshot, EventType.BUDGET_BREACH)
    assert warning_index < breach_index
