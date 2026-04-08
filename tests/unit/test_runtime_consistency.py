"""Unit tests for runtime guardrail consistency helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from runtime.consistency import (
    ConsistencyGuardrailState,
    mark_global_consistency_check_completed,
    prune_consistency_guardrails,
    record_consistency_outcome,
    should_run_global_consistency_check,
)


def test_prune_consistency_guardrails_drops_expired_values() -> None:
    """Pruning should retain only entries that are still active."""

    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = ConsistencyGuardrailState(
        node_cooldowns={
            "active-node": now + timedelta(seconds=20),
            "expired-node": now - timedelta(seconds=1),
        },
        recent_mutation_times=[
            now - timedelta(seconds=12),
            now - timedelta(seconds=3),
        ],
        burst_cooldown_until=now - timedelta(seconds=1),
    )

    pruned = prune_consistency_guardrails(
        state,
        now=now,
        mutation_burst_window=timedelta(seconds=10),
        mutation_burst_trigger_count=2,
    )

    assert pruned.node_cooldowns == {"active-node": now + timedelta(seconds=20)}
    assert pruned.recent_mutation_times == [now - timedelta(seconds=3)]
    assert pruned.burst_cooldown_until is None
    assert pruned.burst_check_pending is False


def test_record_consistency_outcome_sets_global_and_local_cooldowns() -> None:
    """Accepted outcomes should update local and global cooldown state."""

    resolved_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = ConsistencyGuardrailState(
        recent_mutation_times=[resolved_at - timedelta(seconds=5)],
    )

    updated = record_consistency_outcome(
        state,
        candidate_id="node-7",
        resolved_at=resolved_at,
        accepted=True,
        mutation_cooldown=timedelta(seconds=30),
        mutation_burst_trigger_count=2,
        global_mutation_storm_threshold=2,
    )

    assert updated.burst_check_pending is True
    assert updated.burst_cooldown_until == resolved_at + timedelta(seconds=30)
    assert updated.node_cooldowns == {"node-7": resolved_at + timedelta(seconds=30)}


def test_record_consistency_outcome_rejected_does_not_set_node_cooldown() -> None:
    """Rejected outcomes should not set per-node cooldown state."""

    resolved_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = ConsistencyGuardrailState()

    updated = record_consistency_outcome(
        state,
        candidate_id="node-8",
        resolved_at=resolved_at,
        accepted=False,
        mutation_cooldown=timedelta(seconds=30),
        mutation_burst_trigger_count=1,
        global_mutation_storm_threshold=1,
    )

    assert "node-8" not in updated.node_cooldowns
    assert updated.burst_cooldown_until == resolved_at + timedelta(seconds=30)


def test_should_run_global_consistency_check_when_interval_elapsed() -> None:
    """Interval gating should schedule checks only after the configured duration."""

    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = ConsistencyGuardrailState()

    assert (
        should_run_global_consistency_check(
            state,
            now=now,
            global_consistency_check_interval=timedelta(seconds=60),
            last_global_consistency_check_at=now - timedelta(seconds=60),
        )
        is True
    )
    assert (
        should_run_global_consistency_check(
            state,
            now=now,
            global_consistency_check_interval=timedelta(seconds=60),
            last_global_consistency_check_at=now - timedelta(seconds=59),
        )
        is False
    )


def test_should_run_global_consistency_check_when_burst_pending() -> None:
    """Burst-triggered checks should bypass interval gating."""

    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    state = ConsistencyGuardrailState(burst_check_pending=True)

    assert (
        should_run_global_consistency_check(
            state,
            now=now,
            global_consistency_check_interval=timedelta(hours=1),
            last_global_consistency_check_at=now,
        )
        is True
    )


def test_mark_global_consistency_check_completed_clears_burst_pending() -> None:
    """Completing a global check should clear pending burst requests."""

    state = ConsistencyGuardrailState(
        burst_check_pending=True,
        node_cooldowns={"node-1": datetime(2026, 1, 1, 12, 1, tzinfo=timezone.utc)},
        recent_mutation_times=[datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)],
    )

    updated = mark_global_consistency_check_completed(state)

    assert updated.burst_check_pending is False
    assert updated.node_cooldowns == state.node_cooldowns
    assert updated.recent_mutation_times == state.recent_mutation_times
