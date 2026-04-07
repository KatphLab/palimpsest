"""Shared enums and value objects for typed runtime contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.functional_validators import AfterValidator

__all__ = [
    "BudgetTelemetry",
    "CheckStatus",
    "CoherenceSnapshot",
    "DriftCategory",
    "EventOutcome",
    "MutationActionType",
    "MutationEventKind",
    "NodeCoherenceScore",
    "NodeKind",
    "NodeTerminationVote",
    "ProtectionReason",
    "RelationType",
    "SafetyCheckResult",
    "SessionStatus",
    "StrictBaseModel",
    "TerminationVoteState",
    "UTCDateTime",
]


class StrictBaseModel(BaseModel):
    """Base model that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid")


def _to_utc(value: datetime) -> datetime:
    """Normalize timezone-aware datetimes to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")

    return value.astimezone(timezone.utc)


UTCDateTime = Annotated[datetime, AfterValidator(_to_utc)]


class SessionStatus(StrEnum):
    """Lifecycle states for a narrative session."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    FAILED = "failed"


class NodeKind(StrEnum):
    """Kinds of nodes in the narrative graph."""

    SEED = "seed"
    SCENE = "scene"
    BRIDGE = "bridge"
    TERMINATION = "termination"


class DriftCategory(StrEnum):
    """Narrative drift classification."""

    STABLE = "stable"
    WATCH = "watch"
    VOLATILE = "volatile"
    CRITICAL = "critical"


class RelationType(StrEnum):
    """Relationship labels for narrative edges."""

    FOLLOWS = "follows"
    BRANCHES_FROM = "branches_from"
    REINFORCES = "reinforces"
    CONTRADICTS = "contradicts"
    MIRRORS = "mirrors"
    TERMINATES = "terminates"


class ProtectionReason(StrEnum):
    """Reasons an edge or node is protected from mutation."""

    SEED = "seed"
    USER_LOCK = "user_lock"
    SAFETY_GUARD = "safety_guard"


class CheckStatus(StrEnum):
    """Status labels for telemetry and safety checks."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class MutationActionType(StrEnum):
    """Mutation action types proposed by the runtime."""

    ADD_NODE = "add_node"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    REWRITE_NODE = "rewrite_node"
    PRUNE_BRANCH = "prune_branch"
    NO_OP = "no_op"


class MutationEventKind(StrEnum):
    """Mutation audit event kinds."""

    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"
    VETOED = "vetoed"
    COOLED_DOWN = "cooled_down"
    FAILED = "failed"


class EventOutcome(StrEnum):
    """Canonical outcome labels for terminal events."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    WARN = "warn"
    FAIL = "fail"


class NodeCoherenceScore(StrictBaseModel):
    """Local coherence sample for one node."""

    node_id: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    status: CheckStatus | None = None
    sampled_at: UTCDateTime

    @model_validator(mode="after")
    def _populate_status(self) -> NodeCoherenceScore:
        if self.status is None:
            if self.score >= 0.8:
                self.status = CheckStatus.PASS
            elif self.score >= 0.5:
                self.status = CheckStatus.WARN
            else:
                self.status = CheckStatus.FAIL

        return self


class SafetyCheckResult(StrictBaseModel):
    """Single safety check result attached to a mutation decision."""

    check_name: str = Field(min_length=1)
    status: CheckStatus
    message: str = Field(min_length=1)
    details: str | None = None


class NodeTerminationVote(StrictBaseModel):
    """A node-level vote for or against session termination."""

    node_id: str = Field(min_length=1)
    vote: bool
    reason: str | None = None
    recorded_at: UTCDateTime


class CoherenceSnapshot(StrictBaseModel):
    """Current narrative coherence telemetry."""

    global_score: float = Field(ge=0.0, le=1.0)
    local_scores: list[NodeCoherenceScore]
    global_check_status: CheckStatus
    sampled_at: UTCDateTime
    checked_by: str = Field(min_length=1)


class BudgetTelemetry(StrictBaseModel):
    """Session cost and latency telemetry."""

    estimated_cost_usd: Decimal = Field(ge=0)
    budget_limit_usd: Decimal = Field(default=Decimal("5.00"), gt=0)
    token_input_count: int = Field(ge=0)
    token_output_count: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    latency_ms_p50: float | None = Field(default=None, ge=0.0)
    latency_ms_p95: float | None = Field(default=None, ge=0.0)
    soft_warning_emitted: bool = False
    hard_breach_emitted: bool = False


class TerminationVoteState(StrictBaseModel):
    """Aggregate majority-vote state for session termination."""

    active_node_count: int = Field(ge=0)
    votes_for_termination: int = Field(ge=0)
    votes_against_termination: int = Field(ge=0)
    majority_threshold: float = Field(gt=0.5, le=1.0)
    termination_reached: bool = False
    last_updated_at: UTCDateTime | None = None

    @model_validator(mode="after")
    def _sync_termination_state(self) -> TerminationVoteState:
        total_votes = self.votes_for_termination + self.votes_against_termination
        if total_votes > self.active_node_count:
            raise ValueError("vote totals cannot exceed active node count")

        if self.active_node_count == 0:
            self.termination_reached = False
            return self

        self.termination_reached = (
            self.votes_for_termination / self.active_node_count
        ) >= self.majority_threshold
        return self
