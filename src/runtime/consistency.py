"""Pure helper functions for runtime mutation guardrail consistency."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import Field

from models.common import StrictBaseModel, UTCDateTime

__all__ = [
    "ConsistencyGuardrailState",
    "mark_global_consistency_check_completed",
    "prune_consistency_guardrails",
    "record_consistency_outcome",
    "should_run_global_consistency_check",
]


class ConsistencyGuardrailState(StrictBaseModel):
    """Pure value object describing mutation guardrail state."""

    node_cooldowns: dict[str, UTCDateTime] = Field(default_factory=dict)
    recent_mutation_times: list[UTCDateTime] = Field(default_factory=list)
    burst_check_pending: bool = False
    burst_cooldown_until: UTCDateTime | None = None


def _validate_positive_threshold(value: int, *, label: str) -> None:
    """Raise when integer thresholds are not positive."""

    if value < 1:
        raise ValueError(f"{label} must be >= 1")


def _validate_positive_duration(value: timedelta, *, label: str) -> None:
    """Raise when duration thresholds are not positive."""

    if value <= timedelta(0):
        raise ValueError(f"{label} must be > 0")


def should_run_global_consistency_check(
    state: ConsistencyGuardrailState,
    *,
    now: datetime,
    global_consistency_check_interval: timedelta,
    last_global_consistency_check_at: datetime | None,
) -> bool:
    """Return whether a global consistency check should run this cycle."""

    _validate_positive_duration(
        global_consistency_check_interval,
        label="global_consistency_check_interval",
    )

    if state.burst_check_pending:
        return True

    if last_global_consistency_check_at is None:
        return True

    return (now - last_global_consistency_check_at) >= global_consistency_check_interval


def mark_global_consistency_check_completed(
    state: ConsistencyGuardrailState,
) -> ConsistencyGuardrailState:
    """Return guardrail state after a global consistency check completes."""

    return ConsistencyGuardrailState(
        node_cooldowns=dict(state.node_cooldowns),
        recent_mutation_times=list(state.recent_mutation_times),
        burst_check_pending=False,
        burst_cooldown_until=state.burst_cooldown_until,
    )


def prune_consistency_guardrails(
    state: ConsistencyGuardrailState,
    *,
    now: datetime,
    mutation_burst_window: timedelta,
    mutation_burst_trigger_count: int,
) -> ConsistencyGuardrailState:
    """Return a pruned guardrail state for the current timestamp."""

    _validate_positive_threshold(
        mutation_burst_trigger_count,
        label="mutation_burst_trigger_count",
    )

    node_cooldowns = {
        node_id: expires_at
        for node_id, expires_at in state.node_cooldowns.items()
        if expires_at > now
    }
    burst_window_start = now - mutation_burst_window
    recent_mutation_times = [
        mutated_at
        for mutated_at in state.recent_mutation_times
        if mutated_at >= burst_window_start
    ]

    burst_cooldown_until = state.burst_cooldown_until
    if burst_cooldown_until is not None and burst_cooldown_until <= now:
        burst_cooldown_until = None

    return ConsistencyGuardrailState(
        node_cooldowns=node_cooldowns,
        recent_mutation_times=recent_mutation_times,
        burst_cooldown_until=burst_cooldown_until,
        burst_check_pending=(
            len(recent_mutation_times) >= mutation_burst_trigger_count
        ),
    )


def record_consistency_outcome(
    state: ConsistencyGuardrailState,
    *,
    candidate_id: str,
    resolved_at: datetime,
    accepted: bool,
    mutation_cooldown: timedelta,
    mutation_burst_trigger_count: int,
    global_mutation_storm_threshold: int,
) -> ConsistencyGuardrailState:
    """Return updated guardrail state for a resolved mutation decision."""

    _validate_positive_threshold(
        mutation_burst_trigger_count,
        label="mutation_burst_trigger_count",
    )
    _validate_positive_threshold(
        global_mutation_storm_threshold,
        label="global_mutation_storm_threshold",
    )

    recent_mutation_times = [*state.recent_mutation_times, resolved_at]
    burst_cooldown_until = state.burst_cooldown_until

    if len(recent_mutation_times) >= global_mutation_storm_threshold:
        proposed_cooldown_until = resolved_at + mutation_cooldown
        if (
            burst_cooldown_until is None
            or proposed_cooldown_until > burst_cooldown_until
        ):
            burst_cooldown_until = proposed_cooldown_until

    node_cooldowns = dict(state.node_cooldowns)
    if accepted:
        node_cooldowns[candidate_id] = resolved_at + mutation_cooldown

    return ConsistencyGuardrailState(
        node_cooldowns=node_cooldowns,
        recent_mutation_times=recent_mutation_times,
        burst_check_pending=(
            len(recent_mutation_times) >= mutation_burst_trigger_count
        ),
        burst_cooldown_until=burst_cooldown_until,
    )
