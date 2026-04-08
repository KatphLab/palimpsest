"""Integration tests for termination-majority session flow."""

from __future__ import annotations

import pytest

from agents.llm_mutation_proposer import LLMMutationProposer
from agents.scene_agent import SceneAgent
from graph.session_graph import SessionGraph
from models.commands import CommandType, StartSessionCommand, StartSessionPayload
from models.common import SessionStatus, TerminationVoteState
from runtime.session_runtime import SessionRuntime
from tests.fixtures import (
    DeterministicSceneGenerationProvider,
    SequencedMutationProposalProvider,
    build_mutation_response,
)
from utils.time import utc_now

pytestmark = pytest.mark.integration


def test_termination_majority_transitions_session_to_terminating() -> None:
    """A reached termination majority should stop runtime mutation progression."""

    proposal_provider = SequencedMutationProposalProvider(
        responses=[
            lambda prompt: build_mutation_response(
                prompt,
                decision_id="mutation-termination-vote-should-not-run",
            )
        ]
    )
    runtime = SessionRuntime(
        session_graph=SessionGraph(),
        scene_agent=SceneAgent(provider=DeterministicSceneGenerationProvider()),
        mutation_proposer=LLMMutationProposer(provider=proposal_provider),
    )

    start_result = runtime.handle_command(
        StartSessionCommand(
            command_id="cmd-start-termination-001",
            command_type=CommandType.START_SESSION,
            payload=StartSessionPayload(seed_text="A lantern dims at story's edge."),
        )
    )

    assert start_result.accepted is True
    assert runtime.session is not None

    active_node_count = len(runtime.session.active_node_ids)
    runtime.session.termination = TerminationVoteState(
        active_node_count=active_node_count,
        votes_for_termination=active_node_count,
        votes_against_termination=0,
        majority_threshold=0.6,
        last_updated_at=utc_now(),
    )

    decision = runtime.advance_session_cycle()

    assert decision is None
    assert runtime.session.status is SessionStatus.TERMINATING
    assert proposal_provider.prompts == []
