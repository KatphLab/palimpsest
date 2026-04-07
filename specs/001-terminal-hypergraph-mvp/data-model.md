# Data Model: Terminal Self-Editing Narrative MVP

**Spec Version**: 1.2.0

## Modeling assumptions

- Runtime state is owned by a single session-scoped `SessionRuntime`.
- The narrative graph is a `networkx.MultiDiGraph` with stable IDs for nodes and edges.
- All subsystem boundaries use Pydantic v2 models with `extra="forbid"`.
- No plain dictionaries are exchanged between the TUI, the LangGraph runtime, the graph service, or the export layer.
- Runtime mutation proposals are produced by a dedicated LangGraph mutation-proposer subgraph that is separate from scene-generation orchestration.
- Node activation for mutation is LLM-decided and constrained to one activated candidate per mutation cycle.
- Mutation action selection is LLM-decided from explicit narrative context (last two scenes plus graph topology counters), with deterministic fallback.

## Supporting enums and embedded models

### `SessionStatus`

`created`, `running`, `paused`, `terminating`, `terminated`, `failed`.

### `NodeKind`

`seed`, `scene`, `bridge`, `termination`.

### `DriftCategory`

`stable`, `watch`, `volatile`, `critical`.

### `RelationType`

`follows`, `branches_from`, `reinforces`, `contradicts`, `mirrors`, `terminates`.

### `ProtectionReason`

`seed`, `user_lock`, `safety_guard`.

### `CheckStatus`

`pass`, `warn`, `fail`.

### `MutationActionType`

`add_node`, `add_edge`, `remove_edge`, `rewrite_node`, `prune_branch`, `no_op`.

### `MutationEventKind`

`proposed`, `applied`, `rejected`, `vetoed`, `cooled_down`.

### `EventOutcome`

`success`, `blocked`, `warn`, `fail`.

### `NodeCoherenceScore`

| Field | Type | Rules |
|---|---|---|
| `node_id` | `str` | Sampled node identifier |
| `score` | `float` | 0.0-1.0 |
| `status` | `CheckStatus` | Derived from the sampled score |
| `sampled_at` | `datetime` | UTC |

### `SafetyCheckResult`

| Field | Type | Rules |
|---|---|---|
| `check_name` | `str` | Stable safety-check identifier |
| `status` | `CheckStatus` | pass/warn/fail |
| `message` | `str` | Human-readable result |
| `details` | `str | None` | Optional context |

### `NarrativeContext`

| Field | Type | Rules |
|---|---|---|
| `session_id` | `UUID` | Owning session |
| `candidate_node_id` | `str` | Active mutation candidate |
| `recent_scene_texts` | `list[str]` | Exactly the latest two non-empty scene texts when available |
| `node_count` | `int` | >= 0 |
| `edge_count` | `int` | >= 0 |
| `branch_count` | `int` | >= 0 (`relation_type=branches_from`) |
| `graph_version` | `int` | Monotonic per session |

### `MutationActionSelection`

| Field | Type | Rules |
|---|---|---|
| `decision_id` | `str` | Stable id for cycle-local decision |
| `source` | `str` | `llm` or `fallback` |
| `action_type` | `MutationActionType` | Chosen action |
| `reasoning` | `str` | Non-empty natural-language rationale |
| `confidence` | `float` | 0.0-1.0 |
| `suggested_direction` | `str | None` | Optional narrative hint for expansion |

### `NodeTerminationVote`

| Field | Type | Rules |
|---|---|---|
| `node_id` | `str` | Active node identifier |
| `vote` | `bool` | `True` votes to terminate |
| `reason` | `str | None` | Optional explanation |
| `recorded_at` | `datetime` | UTC |

### `GraphExport`

| Field | Type | Rules |
|---|---|---|
| `nodes` | `list[SceneNode]` | Frozen node records |
| `edges` | `list[NarrativeEdge]` | Frozen edge records |
| `root_node_id` | `str | None` | Optional entry point for replay |

### `SessionSummary`

| Field | Type | Rules |
|---|---|---|
| `session_id` | `UUID` | Owning session |
| `status` | `SessionStatus` | Final session status |
| `total_mutations` | `int` | Non-negative |
| `final_coherence` | `float` | 0.0-1.0 |
| `budget_spent_usd` | `Decimal` | Non-negative |
| `ended_at` | `datetime` | UTC |

## Canonical entities

### 1) `Session`

Represents one live narrative run.

| Field | Type | Rules |
|---|---|---|
| `session_id` | `UUID` | Immutable; new value on fork |
| `status` | `SessionStatus` | One of `created`, `running`, `paused`, `terminating`, `terminated`, `failed` |
| `seed_text` | `str` | Required, 1-280 chars, non-whitespace |
| `parent_session_id` | `UUID | None` | Set only for forks |
| `graph_version` | `int` | Monotonic; increments on every accepted mutation |
| `active_node_ids` | `list[str]` | Must reference existing nodes |
| `created_at` / `updated_at` / `ended_at` | `datetime` | UTC timestamps |
| `coherence` | `CoherenceSnapshot` | Required while running |
| `budget` | `BudgetTelemetry` | Required while running |
| `termination` | `TerminationVoteState` | Required while running |

### 2) `SessionSnapshot`

Frozen export-ready copy of a `Session`.

| Field | Type | Rules |
|---|---|---|
| `session_id` | `UUID` | Same as the source session |
| `status` | `SessionStatus` | Captured at export time |
| `seed_text` | `str` | Same validation as `Session` |
| `parent_session_id` | `UUID | None` | Preserved from source |
| `graph_version` | `int` | Snapshot version |
| `active_node_ids` | `list[str]` | Frozen copy of live state |
| `created_at` / `updated_at` / `ended_at` | `datetime` | Captured UTC timestamps |
| `coherence` | `CoherenceSnapshot` | Frozen copy |
| `budget` | `BudgetTelemetry` | Frozen copy |
| `termination` | `TerminationVoteState` | Frozen copy |
| `captured_at` | `datetime` | UTC export capture time |

### 3) `SceneNode`

Represents a narrative unit and its runtime telemetry.

| Field | Type | Rules |
|---|---|---|
| `node_id` | `str` | Stable within session |
| `session_id` | `UUID` | Must match owning session |
| `node_kind` | `NodeKind` | `seed`, `scene`, `bridge`, `termination` |
| `text` | `str` | Required, non-empty |
| `entropy_score` | `float` | 0.0-1.0 |
| `drift_category` | `DriftCategory` | `stable`, `watch`, `volatile`, `critical` |
| `activation_count` | `int` | >= 0 |
| `last_activated_at` | `datetime | None` | UTC |
| `is_seed_protected` | `bool` | True for the seed node |
| `termination_vote` | `NodeTerminationVote | None` | Only for active nodes |

### 4) `NarrativeEdge`

Represents a directed relationship between nodes.

| Field | Type | Rules |
|---|---|---|
| `edge_id` | `str` | Stable within session |
| `session_id` | `UUID` | Must match owning session |
| `source_node_id` | `str` | Must exist |
| `target_node_id` | `str` | Must exist |
| `relation_type` | `RelationType` | `follows`, `branches_from`, `reinforces`, `contradicts`, `mirrors`, `terminates` |
| `locked` | `bool` | Locked edges cannot be removed |
| `protected_reason` | `ProtectionReason | None` | `seed`, `user_lock`, `safety_guard` |
| `relation_group_id` | `str | None` | Shared by bundled narrative links |
| `provenance_event_id` | `str` | Mutation event that created the edge |

### 5) `MutationDecision`

Represents one proposed change from the LangGraph mutation branch.

Action semantics:

- `add_node`: creates one new node and requires immediate scene text generation in the same cycle once accepted.
- `add_edge`: creates one directed relationship between existing nodes.
- `remove_edge`: removes one mutable relationship edge.
- `rewrite_node`: rewrites scene text for one existing node.
- `prune_branch`: removes the full subgraph rooted at the targeted branch root, excluding seed-protected and otherwise protected graph state.
- `no_op`: explicit no-change cycle outcome.

| Field | Type | Rules |
|---|---|---|
| `decision_id` | `str` | Unique per proposal |
| `session_id` | `UUID` | Owning session |
| `actor_node_id` | `str` | Node that proposed the change |
| `target_ids` | `list[str]` | Node and/or edge IDs affected |
| `action_type` | `MutationActionType` | `add_node`, `add_edge`, `remove_edge`, `rewrite_node`, `prune_branch`, `no_op` |
| `risk_score` | `float` | 0.0-1.0 |
| `safety_checks` | `list[SafetyCheckResult]` | Must be non-empty for non-`no_op` actions |
| `accepted` | `bool` | Set only after safety filter |
| `rejected_reason` | `str | None` | Required when rejected |

`MutationDecision` is derived from `MutationActionSelection` plus runtime targeting and safety filtering.

### 6) `MutationEvent`

Append-only canonical audit record for all mutation activity. The terminal event stream uses the
transport-specific name `MutationStreamEvent`, but maps to this shape for export and replay.

| Field | Type | Rules |
|---|---|---|
| `event_id` | `str` | Unique and immutable |
| `sequence` | `int` | Strictly monotonic per session |
| `session_id` | `UUID` | Owning session |
| `event_kind` | `MutationEventKind` | `proposed`, `applied`, `rejected`, `vetoed`, `cooled_down` |
| `actor_node_id` | `str | None` | Required for agent-driven actions |
| `target_ids` | `list[str]` | Must reference valid IDs when present |
| `outcome` | `EventOutcome` | `success`, `blocked`, `warn`, `fail` |
| `reason` | `str` | Required for rejected or vetoed outcomes |
| `occurred_at` | `datetime` | UTC |

### 7) `CoherenceSnapshot`

Records the current health of the narrative topology.

| Field | Type | Rules |
|---|---|---|
| `global_score` | `float` | 0.0-1.0; target >= 0.80 |
| `local_scores` | `list[NodeCoherenceScore]` | One entry per sampled node |
| `global_check_status` | `CheckStatus` | `pass`, `warn`, `fail` |
| `sampled_at` | `datetime` | UTC |
| `checked_by` | `str` | `local`, `global`, or named check stage |

### 8) `BudgetTelemetry`

Tracks session cost and latency.

| Field | Type | Rules |
|---|---|---|
| `estimated_cost_usd` | `Decimal` | Non-negative |
| `budget_limit_usd` | `Decimal` | Default target: 5.00 |
| `token_input_count` | `int` | >= 0 |
| `token_output_count` | `int` | >= 0 |
| `model_call_count` | `int` | >= 0 |
| `latency_ms_p50` | `float | None` | Optional runtime metric |
| `latency_ms_p95` | `float | None` | Optional runtime metric |
| `soft_warning_emitted` | `bool` | True after warning threshold |
| `hard_breach_emitted` | `bool` | True after budget exceedance |

### 9) `TerminationVoteState`

Aggregates active-node termination votes.

| Field | Type | Rules |
|---|---|---|
| `active_node_count` | `int` | >= 0 |
| `votes_for_termination` | `int` | >= 0 |
| `votes_against_termination` | `int` | >= 0 |
| `majority_threshold` | `float` | 0.5 < threshold <= 1.0 |
| `termination_reached` | `bool` | Derived from vote ratio |
| `last_updated_at` | `datetime | None` | UTC |

### 10) `ExportArtifact`

Structured JSON export of a session snapshot.

| Field | Type | Rules |
|---|---|---|
| `schema_version` | `str` | Versioned contract string |
| `exported_at` | `datetime` | UTC |
| `session` | `SessionSnapshot` | Frozen snapshot |
| `graph` | `GraphExport` | Nodes, edges, metadata |
| `events` | `list[MutationEvent]` | Chronological, append-only |
| `summary` | `SessionSummary` | Final state and key metrics |

## Relationships

- A `Session` owns many `SceneNode` records and many `NarrativeEdge` records.
- A `Session` owns exactly one `BudgetTelemetry`, one `CoherenceSnapshot`, and one `TerminationVoteState` snapshot at a time.
- A `MutationDecision` may produce zero or one `MutationEvent` outcome record.
- A `MutationEvent` may target one or more nodes or edges, but it must always resolve to a valid session-owned ID set.
- An `ExportArtifact` is derived from a frozen `SessionSnapshot`, not from live mutable state.

## Validation rules

1. `seed_text` must be 1-280 characters and cannot be blank.
2. Session snapshots are immutable; live runtime state must be copied before export.
3. `node_id` and `edge_id` values must be unique within a session.
4. Locked edges cannot be removed or rewritten by autonomous mutation.
5. The seed node is immutable after creation and cannot be deleted.
6. At most one mutation proposal may be produced and resolved per mutation cycle.
7. Mutation cooldown must suppress rapid repeated changes on the same branch.
8. Coherence and budget models must be present for every running session snapshot.
9. Event sequence numbers must be strictly increasing without gaps in a single session log.
10. `votes_for_termination + votes_against_termination` must never exceed `active_node_count`.
11. All structured models must reject extra fields.
12. `add_node` decisions must produce a non-empty scene text for the created node before the cycle is considered complete.
13. `prune_branch` must target a valid branch root and may not remove seed-protected or otherwise protected graph state.
14. LLM mutation action selection must receive `NarrativeContext` including up to two recent scene texts plus graph node/edge/branch counts.
15. If LLM selection fails validation, runtime must use deterministic fallback and mark selection `source=fallback`.

## State transitions

### Session lifecycle

`created -> running -> paused -> running -> terminating -> terminated`

- `running -> paused` on user pause.
- `paused -> running` on user resume.
- `running -> terminating` when termination voting exceeds the configured majority threshold.
- `terminating -> terminated` after final summary and export are emitted.
- `running -> failed` on unrecoverable runtime error.

### Scene node lifecycle

`seed_created -> active -> cooling_down -> active -> archived`

- The seed node starts in protected active state.
- A node enters `cooling_down` after it receives an activation mutation.
- Cooling-down nodes cannot be mutated again until the cooldown window expires.
- Archived nodes remain readable in export artifacts but do not participate in live votes.

### Narrative edge lifecycle

`draft -> active -> locked -> active -> removed`

- `locked` is an orthogonal protection state, not a separate edge identity.
- A locked edge may be unlocked by the user, then removed only if it is no longer protected.
- Protected edges created from the seed relation cannot be removed during autonomous mutation.

### Mutation decision lifecycle

`proposed -> safety_passed -> applied | rejected | cooled_down`

- `safety_passed` is required before an action can alter the graph.
- `applied` increments the session graph version.
- `rejected` and `cooled_down` still append event-log records for traceability.
- The mutation-proposer subgraph selects one activation candidate and emits at most one proposal per cycle.
- When `action_type=add_node`, scene generation is immediate and part of the same applied mutation cycle.

## Requirement alignment

- FR-001/FR-002: `Session.seed_text`, `Session.status`, and `TerminalCommand` start-session input.
- FR-003/FR-004: `Session` snapshots, `graph_version`, explicit cycle advancement, and pause/resume transitions.
- FR-005/FR-006: `NarrativeEdge.locked` and `protected_reason`.
- FR-007: `parent_session_id` and forked `Session` snapshot derivation.
- FR-008/FR-010: `SceneNode.entropy_score`, `drift_category`, and inspection snapshot fields.
- FR-009: `MutationEvent.sequence`, actor, target, and outcome fields.
- FR-011: `ExportArtifact` and `SessionSnapshot`.
- FR-012/FR-013: mutation safety fields, cooldown, and coherence checks.
- FR-014: `TerminationVoteState` and session termination transitions.
- FR-015: `BudgetTelemetry`.
- FR-016/FR-017/FR-018: dedicated mutation-proposer flow, single-node activation, and one proposal resolution per cycle.
- FR-019: immediate scene generation requirements for accepted `add_node` actions.
- FR-020: `prune_branch` subgraph semantics with protection guardrails.
- FR-023/FR-024: `NarrativeContext` and `MutationActionSelection` define LLM action-decision inputs and outputs for boring-vs-interesting mutation choice.
- FR-025: deterministic fallback is captured by `MutationActionSelection.source` (`llm` or `fallback`).
- FR-026: mutation decision telemetry fields (`source`, `action_type`, `confidence`, `reasoning`) are first-class typed data.
- CA-001: `CoherenceSnapshot.global_score` and periodic checks.
- CA-002: seed immutability, locked-edge protection, mutation caps, cooldown.
- CA-003: all models are typed Pydantic contracts.
- CA-004: the contract boundaries are explicit and testable.
- CA-005: budget telemetry and hard/soft breach state.
