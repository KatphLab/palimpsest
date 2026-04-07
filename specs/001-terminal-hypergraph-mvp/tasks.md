# Tasks: Terminal Self-Editing Narrative MVP

**Spec Version**: 1.2.0

**Input**: Design documents from `/specs/001-terminal-hypergraph-mvp/`
**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Tests are REQUIRED by CA-004 and plan.md test-first gate expansion. For each user story, write failing tests before implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (for example, `US1`, `US2`, `US3`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and baseline structure for the terminal MVP runtime.

- [x] T001 Create runtime module scaffolding in `src/agents/__init__.py`, `src/models/__init__.py`, `src/runtime/__init__.py`, and `src/tui/__init__.py`
- [x] T002 Add runtime dependencies (`networkx`, `langgraph`, `langchain-openai`, `textual`, `pydantic-settings`) to `pyproject.toml`
- [x] T003 Configure pytest discovery and markers for `unit`, `integration`, and `contracts` in `pyproject.toml`
- [x] T004 [P] Create test package scaffolding in `tests/unit/__init__.py`, `tests/integration/__init__.py`, and `tests/contracts/__init__.py`
- [x] T005 Define default runtime constants and validated settings fields in `src/config/env.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core contracts and runtime primitives that MUST be complete before ANY user story implementation.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Write failing base model validation tests for enums, timestamps, and `extra="forbid"` behavior in `tests/unit/test_models_base.py`
- [x] T007 [P] Write failing discriminated command envelope mismatch tests in `tests/contracts/test_terminal_command_contract.py`
- [x] T008 [P] Write failing event envelope monotonic-sequence tests in `tests/contracts/test_event_stream_envelope_base.py`
- [x] T009 Implement shared enums and value objects (`SessionStatus`, `DriftCategory`, `EventOutcome`) in `src/models/common.py`
- [x] T010 Implement command envelope and payload union models in `src/models/commands.py`
- [x] T011 [P] Implement canonical event stream models and envelope contracts in `src/models/events.py`
- [x] T012 Implement `SessionGraph` service skeleton with typed add/remove/lock primitives in `src/graph/session_graph.py`
- [x] T013 Implement `SessionRuntime` command router skeleton and state ownership boundaries in `src/runtime/session_runtime.py`
- [x] T014 Wire `src/main.py` to start runtime in Textual mode with CLI fallback entry path

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Seed and Step Narrative Growth (Priority: P1) 🎯 MVP

**Goal**: Let a user start a session from a valid seed and step deterministic narrative growth with pause/resume controls.

**Independent Test**: Start one session with a valid seed, verify first scene appears within 2 seconds, verify no background auto-advance, then use continue to advance one cycle at a time and pause/resume without losing session state.

### Tests for User Story 1 (REQUIRED)

- [x] T015 [P] [US1] Write failing integration test for seed-to-first-scene latency in `tests/integration/test_seed_startup_flow.py`
- [x] T016 [P] [US1] Write failing integration test to verify no background auto-advance without a manual cycle in `tests/integration/test_autonomous_progress_after_start.py`
- [x] T017 [P] [US1] Write failing integration test for pause/resume state continuity in `tests/integration/test_pause_resume_flow.py`
- [x] T018 [P] [US1] Write failing command contract tests for `start_session`, `pause_session`, and `resume_session` in `tests/contracts/test_session_control_commands.py`

### Implementation for User Story 1

- [x] T019 [P] [US1] Implement `Session` and `SessionSnapshot` models with seed validation in `src/models/session.py`
- [x] T020 [P] [US1] Implement `SceneNode` model and activation metadata rules in `src/models/node.py`
- [x] T021 [P] [US1] Implement seed bootstrapping and first-scene generation agent in `src/agents/scene_agent.py`
- [x] T022 [US1] Implement session cycle advancement entrypoint (`advance_session_cycle`) and pause/resume transitions in `src/runtime/session_runtime.py`
- [x] T023 [US1] Implement TUI app shell with manual panel refresh callback and continue-cycle action in `src/tui/app.py`
- [x] T024 [US1] Implement seed entry and pause/resume interaction handlers in `src/tui/screens.py`
- [x] T058 [US1] Implement deterministic story-flow projection renderer for seed/mainline/branch/detached sections in `src/tui/story_projection.py`
- [x] T059 [US1] Add TUI integration coverage for growing story-flow rendering and detached scene projection in `tests/integration/test_live_story_flow_rendering.py` and `tests/unit/test_tui_story_projection.py`

**Checkpoint**: User Story 1 is independently functional and testable.

---

## Phase 4: User Story 2 - Intervene in Narrative Topology (Priority: P2)

**Goal**: Let a user lock/unlock narrative edges and fork sessions while preserving mutation safety and session independence.

**Independent Test**: Lock an existing edge and verify it survives mutation cycles, then fork the session and confirm both sessions evolve independently.

### Tests for User Story 2 (REQUIRED)

- [x] T025 [P] [US2] Write failing integration test for locked-edge protection during mutation cycles in `tests/integration/test_locked_edge_protection.py`
- [x] T026 [P] [US2] Write failing integration test for forked-session isolation and independent graph versions in `tests/integration/test_fork_session_isolation.py`
- [x] T027 [P] [US2] Write failing command contract tests for `lock_edge`, `unlock_edge`, and `fork_session` in `tests/contracts/test_topology_control_commands.py`

### Implementation for User Story 2

- [x] T028 [P] [US2] Implement `NarrativeEdge` model with lock/protection invariants in `src/models/edge.py`
- [x] T029 [P] [US2] Implement mutation proposal model and safety gate checks in `src/models/mutation.py`
- [x] T030 [P] [US2] Implement mutation safety filter and lock-aware edge operations in `src/agents/mutation_agent.py`
- [x] T031 [US2] Implement runtime handlers for lock, unlock, and fork commands in `src/runtime/session_runtime.py`
- [x] T032 [US2] Implement TUI controls for edge locking and session switching in `src/tui/widgets.py`

### Follow-up Implementation for User Story 2 (Autonomous Mutation Cycle)

- [x] T048 [P] [US2] Write failing unit tests for LangGraph mutation proposer subgraph with single-node activation in `tests/unit/test_mutation_engine.py`
- [x] T049 [P] [US2] Write failing integration test for one-mutation-per-cycle enforcement in `tests/integration/test_single_mutation_cycle.py`
- [x] T050 [P] [US2] Write failing integration test for immediate scene generation on accepted `add_node` mutation in `tests/integration/test_add_node_immediate_generation.py`
- [x] T051 [P] [US2] Write failing integration test for `prune_branch` full-subgraph removal with protected-state guardrails in `tests/integration/test_prune_branch_subgraph.py`
- [x] T052 [P] [US2] Implement dedicated mutation proposer LangGraph subgraph in `src/agents/mutation_engine.py`
- [x] T053 [US2] Extend mutation apply path for all action types (`add_node`, `add_edge`, `remove_edge`, `rewrite_node`, `prune_branch`, `no_op`) in `src/agents/mutation_agent.py`
- [x] T054 [US2] Extend scene agent APIs for immediate generation after accepted `add_node` and rewrite support in `src/agents/scene_agent.py`
- [x] T055 [US2] Implement runtime mutation orchestration loop (propose -> review -> apply -> emit outcome) in `src/runtime/session_runtime.py`
- [x] T056 [US2] Implement node cooldown and mutation burst guardrails in runtime loop state in `src/runtime/session_runtime.py`
- [x] T057 [US2] Emit mutation lifecycle events (`proposed`, `applied`, `rejected`, `cooled_down`) with monotonic sequencing in `src/runtime/session_runtime.py`

**Checkpoint**: User Story 2 is independently functional and testable, including explicit cycle-based mutation orchestration.

---

## Phase 4.5: LLM Mutation Strategy Layer (Pre-US3)

**Purpose**: Replace static mutation action proposal heuristics with an LLM-driven action selector that evaluates narrative context, while preserving deterministic fallback and mutation safety.

### Tests for Phase 4.5 (REQUIRED)

- [ ] T060 [P] [US2] Write failing unit tests for narrative-context extraction (last two scenes + graph counters) in `tests/unit/test_narrative_context_builder.py`
- [ ] T061 [P] [US2] Write failing unit tests for LLM mutation-action selection parsing and validation in `tests/unit/test_llm_mutation_proposer.py`
- [ ] T062 [P] [US2] Write failing unit tests for deterministic fallback selection when LLM output is invalid/unavailable in `tests/unit/test_deterministic_mutation_proposer.py`
- [ ] T063 [P] [US2] Write failing integration test proving repeated continue actions can grow beyond two scenes in `tests/integration/test_llm_mutation_progression.py`
- [ ] T064 [P] [US2] Write failing integration test for decision-log emission to console and `app.log` in `tests/integration/test_mutation_decision_logging.py`

### Implementation for Phase 4.5

- [ ] T065 [P] [US2] Implement typed narrative context models in `src/models/narrative_context.py`
- [ ] T066 [P] [US2] Implement narrative context builder from live graph/session state in `src/agents/narrative_context_builder.py`
- [ ] T067 [P] [US2] Implement deterministic mutation proposer fallback in `src/agents/deterministic_mutation_proposer.py`
- [ ] T068 [US2] Implement LLM mutation proposer with structured-output parsing and fallback routing in `src/agents/llm_mutation_proposer.py`
- [ ] T069 [US2] Integrate LLM mutation proposer into runtime mutation-cycle orchestration in `src/runtime/session_runtime.py`
- [ ] T070 [US2] Update logging configuration for mutation-decision telemetry in both console and rotating file handlers in `src/config/logging_config.py`

**Checkpoint**: LLM-driven mutation action selection is active with deterministic fallback, and decision telemetry is visible in both console and file logs.

---

## Phase 5: User Story 3 - Inspect Entropy and Mutation Decisions (Priority: P3)

**Goal**: Let a user monitor entropy/mutation decisions, inspect node details, and export complete typed session artifacts.

**Independent Test**: Run a session until mutations occur, inspect node details with entropy/drift context, verify chronological event log output, and export a valid JSON artifact.

### Tests for User Story 3 (REQUIRED)

- [ ] T033 [P] [US3] Write failing contract tests for mutation stream ordering and `target_ids` semantics in `tests/contracts/test_event_stream_contract.py`
- [ ] T034 [P] [US3] Write failing contract tests for export artifact schema and required fields in `tests/contracts/test_export_artifact_contract.py`
- [ ] T035 [P] [US3] Write failing integration test for entropy monitoring and node inspection flow in `tests/integration/test_entropy_inspection_flow.py`
- [ ] T036 [P] [US3] Write failing integration test for budget warning/breach alerts in `tests/integration/test_budget_alerting_flow.py`
- [ ] T037 [P] [US3] Write failing integration test for export command path validation and artifact completeness in `tests/integration/test_export_session_flow.py`

### Implementation for User Story 3

- [ ] T038 [P] [US3] Implement coherence and budget telemetry models in `src/models/telemetry.py`
- [ ] T039 [P] [US3] Implement export artifact builders and atomic file writer in `src/runtime/exporter.py`
- [ ] T040 [US3] Implement mutation event append-only stream with monotonic sequence IDs in `src/runtime/event_log.py`
- [ ] T041 [US3] Implement runtime inspect/export/telemetry command handlers in `src/runtime/session_runtime.py`
- [ ] T042 [US3] Implement TUI mutation log, entropy hotspot view, and node detail panel in `src/tui/widgets.py`

**Checkpoint**: User Story 3 is independently functional and testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, performance, and documentation updates affecting multiple stories.

- [ ] T043 [P] Implement global consistency interval and mutation-burst trigger checks in `src/runtime/consistency.py`
- [ ] T044 [P] Add integration coverage for termination-majority end-of-session behavior in `tests/integration/test_termination_vote_flow.py`
- [ ] T045 Harden runtime error handling for invalid IDs and non-writable export paths in `src/runtime/session_runtime.py`
- [ ] T046 Update terminal command usage and troubleshooting notes in `README.md`
- [ ] T047 Tune and document production defaults for refresh, cooldown, coherence, and budget limits in `src/config/env.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies
- Foundational (Phase 2): depends on Setup completion and blocks all user stories
- User Story phases (Phases 3-5): each depends on Foundational completion
- Phase 4.5 depends on US2 mutation-orchestration completion and blocks US3 observability implementation to avoid rework.
- Polish (Phase 6): depends on completion of the target user stories

### User Story Dependencies

- US1 (P1): starts immediately after Foundational; delivers MVP runtime value
- US2 (P2): starts after Foundational; lock/fork controls are independent, while autonomous mutation-cycle follow-up tasks depend on US1 runtime loop and scene generation contracts
- Phase 4.5 (pre-US3): starts after US2 mutation-cycle tasks; introduces LLM mutation action strategy and logging telemetry
- US3 (P3): starts after Phase 4.5 so observability surfaces align with finalized mutation-decision telemetry

### Within Each User Story

- Tests first and intentionally failing before implementation
- Models and contracts before runtime handlers
- Runtime handlers before TUI wiring
- Story checkpoint validation before moving to next phase

---

## Parallel Opportunities

- Setup: T004 can run in parallel with T005 after T001
- Foundational: T007, T008, and T011 can run in parallel once T006 is written
- US1: T015-T018 can run in parallel; T019-T021 can run in parallel; T058 and T059 can run in parallel after T023
- US2: T025-T027 can run in parallel; T028-T030 can run in parallel
- US2 follow-up: T048-T051 can run in parallel; T052 and T054 can run in parallel before T055-T057
- Phase 4.5: T060-T064 can run in parallel; T065-T067 can run in parallel before T068-T070
- US3: T033-T037 can run in parallel; T038-T039 can run in parallel
- Polish: T043 and T044 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Run independent failing tests first:
Task: "T015 [US1] tests/integration/test_seed_startup_flow.py"
Task: "T016 [US1] tests/integration/test_autonomous_progress_after_start.py"
Task: "T017 [US1] tests/integration/test_pause_resume_flow.py"
Task: "T018 [US1] tests/contracts/test_session_control_commands.py"

# Then parallelize model and agent implementation:
Task: "T019 [US1] src/models/session.py"
Task: "T020 [US1] src/models/node.py"
Task: "T021 [US1] src/agents/scene_agent.py"
```

## Parallel Example: User Story 2

```bash
# Independent tests in parallel:
Task: "T025 [US2] tests/integration/test_locked_edge_protection.py"
Task: "T026 [US2] tests/integration/test_fork_session_isolation.py"
Task: "T027 [US2] tests/contracts/test_topology_control_commands.py"

# Independent model/agent tasks in parallel:
Task: "T028 [US2] src/models/edge.py"
Task: "T029 [US2] src/models/mutation.py"
Task: "T030 [US2] src/agents/mutation_agent.py"
```

## Parallel Example: User Story 3

```bash
# Independent tests in parallel:
Task: "T033 [US3] tests/contracts/test_event_stream_contract.py"
Task: "T034 [US3] tests/contracts/test_export_artifact_contract.py"
Task: "T035 [US3] tests/integration/test_entropy_inspection_flow.py"
Task: "T036 [US3] tests/integration/test_budget_alerting_flow.py"
Task: "T037 [US3] tests/integration/test_export_session_flow.py"

# Parallel implementation tasks before runtime/TUI integration:
Task: "T038 [US3] src/models/telemetry.py"
Task: "T039 [US3] src/runtime/exporter.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phases 1 and 2.
2. Complete Phase 3 (US1) only.
3. Validate US1 independently against latency, refresh, and pause/resume criteria.
4. Demo/deploy MVP before expanding scope.

### Incremental Delivery

1. Foundation ready (Phases 1-2).
2. Deliver US1 and validate independently.
3. Deliver US2 and validate lock/fork independence.
4. Deliver Phase 4.5 LLM mutation strategy and validate >2-scene progression plus decision logging.
5. Deliver US3 and validate observability/export coverage.
6. Finish with Polish tasks for global checks and documentation.

### Parallel Team Strategy

1. Team aligns on shared foundational contracts first.
2. After Phase 2, assign US1/US2/US3 to different developers with coordination on shared runtime files.
3. Merge at story checkpoints, not mid-story, to preserve independent testability.
