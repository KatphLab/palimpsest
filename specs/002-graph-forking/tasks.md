# Tasks: Graph Forking with Multi-Graph View

**Input**: Design documents from `/specs/002-graph-forking/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Feature Branch**: `002-graph-forking`
**Generated**: 2026-04-08

**Tests**: Tests are REQUIRED per Constitution CA-004. Write failing tests before implementation tasks for each user story.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure per plan.md

- [X] T001 Verify Python 3.12+ environment and uv installation
- [X] T002 [P] Create directory structure per plan.md project structure section in src/ and tests/
- [X] T003 [P] Create models package with __init__.py at src/models/
- [X] T004 [P] Create services package with __init__.py at src/services/
- [X] T005 [P] Create persistence package with __init__.py at src/persistence/
- [X] T006 [P] Create runtime package with __init__.py at src/runtime/
- [X] T007 [P] Create cli package with __init__.py at src/cli/commands/ and src/cli/ui/
- [X] T008 [P] Create tests/unit/models/, tests/unit/services/, tests/integration/, tests/contract/ directories

**Checkpoint**: Project structure matches plan.md, ready for foundational implementation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Base Entity Models (All Stories Depend On These)

- [X] T009 [P] Create ForkPoint entity in src/models/fork_point.py with validation per data-model.md
- [X] T010 [P] Create SeedConfiguration entity in src/models/seed_config.py with auto-generation logic per data-model.md
- [X] T011 [P] Create GraphLineage entity in src/models/graph_lineage.py with tree structure per data-model.md
- [X] T012 [P] Create GraphSummary entity in src/models/multi_graph_view.py (lightweight representation per data-model.md)
- [X] T013 Create GraphInstance entity in src/models/graph_instance.py (depends on T009, T010, references ForkPoint and SeedConfiguration)

### Persistence Foundation

- [X] T014 [P] Create graph storage schema in src/persistence/graph_store.py with JSON serialization per data-model.md persistence mapping
- [X] T015 [P] Create lineage storage schema in src/persistence/lineage_store.py for fork ancestry per data-model.md
- [X] T016 Implement GraphStore class with save/load/delete operations in src/persistence/graph_store.py
- [X] T017 Implement LineageStore class with ancestry tracking in src/persistence/lineage_store.py

### Utility Infrastructure

- [X] T018 [P] Create coherence scorer utility in src/services/coherence_scorer.py per CA-001 (>0.7 threshold)
- [X] T019 [P] Create structured logging utility for operation tracking per SC-009
- [X] T020 Create UUID validation utilities for model validation per contract patterns

**Checkpoint**: Foundation ready - GraphInstance, ForkPoint, SeedConfiguration, GraphLineage models exist with persistence. User story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Fork Graph at Edge (Priority: P1) 🎯 MVP

**Goal**: Enable users to create narrative graph forks at any edge, creating parallel graph instances that share history up to the fork point but diverge independently.

**Independent Test**: Create a fork from any edge in an active graph, verify new parallel graph instance is created sharing history up to that edge, verify original graph unaffected.

### Tests for User Story 1 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T021 [P] [US1] Contract test for GraphForkRequest/GraphForkResponse in tests/contract/test_graph_forking.py per contracts/graph-forking.md
- [X] T022 [P] [US1] Unit test for ForkPoint validation in tests/unit/models/test_fork_point.py per data-model.md validation rules
- [X] T023 [P] [US1] Unit test for SeedConfiguration auto-generation in tests/unit/models/test_seed_config.py
- [X] T024 [US1] Integration test for fork isolation (verify parent and fork are independent) in tests/integration/test_fork_isolation.py
- [X] T025 [US1] Integration test for fork immutability (history frozen) in tests/integration/test_fork_isolation.py per CA-002

### Implementation for User Story 1

- [X] T026 [US1] Implement GraphForkRequest Pydantic model in src/models/requests.py per contracts/graph-forking.md
- [X] T027 [US1] Implement GraphForkResponse Pydantic model in src/models/responses.py per contracts/graph-forking.md
- [X] T028 [US1] Implement GraphForker service with fork_graph() method in src/services/graph_forker.py per plan.md and contracts/graph-forking.md
- [X] T029 [US1] Implement fork validation logic in GraphForker.validate_fork_request() per contracts/graph-forking.md
- [X] T030 [US1] Implement deep copy of graph structure up to fork edge in src/services/graph_forker.py per research.md Decision 1
- [X] T031 [US1] Implement GraphLineage creation during fork in src/services/graph_forker.py per data-model.md fork flow
- [X] T032 [US1] Implement ForkErrorCode enum and GraphForkError in src/models/errors.py per contracts/graph-forking.md
- [X] T033 [US1] Add structured logging for fork operations with timestamps per SC-009
- [X] T034 [US1] Implement CLI fork command in src/cli/commands/fork.py per plan.md
- [X] T035 [US1] Add fork progress indicator in CLI per acceptance scenario SC-001 (<3 clicks/keystrokes)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Fork creation works, isolation verified, immutability enforced.

---

## Phase 4: User Story 2 - View and Switch Between Graphs (Priority: P1)

**Goal**: Provide visual overview of all active graph instances and enable efficient switching between them for managing multiple parallel narrative threads.

**Independent Test**: Create multiple forks, open multi-graph view, verify all graphs visible with metadata, select any graph to switch to it, verify correct state loads within 500ms.

### Tests for User Story 2 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T036 [P] [US2] Contract test for MultiGraphView/GraphSummary in tests/contract/test_multi_graph_view.py per contracts/multi-graph-view.md
- [X] T037 [P] [US2] Contract test for GraphSwitchRequest/GraphSwitchResponse in tests/contract/test_multi_graph_view.py
- [X] T038 [P] [US2] Unit test for GraphSummary model in tests/unit/models/test_multi_graph_view.py
- [X] T039 [US2] Integration test for multi-graph view returns all active graphs in tests/integration/test_multi_graph_view.py
- [X] T040 [US2] Integration test for graph switch loads correct state in tests/integration/test_multi_graph_view.py
- [X] T041 [US2] Performance test for multi-graph view <200ms with 50 graphs per CA-005

### Implementation for User Story 2

- [X] T042 [US2] Implement ViewPreferences Pydantic model in src/models/views.py per contracts/multi-graph-view.md
- [X] T043 [US2] Implement FilterState Pydantic model in src/models/views.py per contracts/multi-graph-view.md and data-model.md
- [X] T044 [US2] Implement MultiGraphView Pydantic model in src/models/views.py per contracts/multi-graph-view.md
- [X] T045 [US2] Implement GraphSwitchRequest/GraphSwitchResponse in src/models/requests.py and src/models/responses.py per contracts/multi-graph-view.md
- [X] T046 [US2] Implement GraphManager service with get_multi_graph_view() in src/services/graph_manager.py per plan.md
- [X] T047 [US2] Implement filtering and sorting in GraphManager per FilterState specification
- [X] T048 [US2] Implement graph switch logic in src/services/graph_switcher.py per plan.md and contracts/multi-graph-view.md
- [X] T049 [US2] Implement optimistic locking with lastModified timestamp per research.md Decision 6 and spec clarification
- [X] T050 [US2] Implement delete_graph() and archive_graph() in GraphManager per contracts/multi-graph-view.md
- [X] T051 [US2] Implement CLI list_graphs command in src/cli/commands/list_graphs.py per plan.md
- [X] T052 [US2] Implement CLI switch_graph command in src/cli/commands/switch_graph.py per plan.md
- [X] T053 [US2] Implement multi_graph_display terminal UI in src/cli/ui/multi_graph_display.py per plan.md
- [X] T054 [US2] Add search/filter CLI options to list_graphs command per acceptance scenario 3
- [X] T055 [US2] Add structured logging for switch/list/delete operations per SC-009

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently. Multi-graph view shows all graphs, switching works within 500ms, filtering works.

---

## Phase 5: User Story 3 - Parallel Graph Execution (Priority: P2)

**Goal**: Enable multiple graph instances to run independently in parallel so users can explore different narrative outcomes simultaneously without blocking.

**Independent Test**: Create two forks, advance each graph independently, verify state changes in one do not affect the other, verify both can progress simultaneously.

### Tests for User Story 3 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T056 [P] [US3] Contract test for ExecutionState/ParallelExecutionState in tests/contract/test_parallel_execution.py per contracts/parallel-execution.md
- [X] T057 [P] [US3] Integration test for parallel execution maintains isolation in tests/integration/test_parallel_execution.py per contracts/parallel-execution.md isolation contract
- [X] T058 [US3] Integration test for rapid graph switching maintains independent state per acceptance scenario 2
- [X] T059 [US3] Integration test for background operations don't block foreground per acceptance scenario 3

### Implementation for User Story 3

- [X] T060 [US3] Implement ExecutionStatus enum in src/models/execution.py per contracts/parallel-execution.md
- [X] T061 [US3] Implement ExecutionState Pydantic model in src/models/execution.py per contracts/parallel-execution.md
- [X] T062 [US3] Implement ParallelExecutionState Pydantic model in src/models/execution.py per contracts/parallel-execution.md
- [X] T063 [US3] Implement MultiGraphExecutor service in src/runtime/multi_graph_executor.py per plan.md
- [X] T064 [US3] Implement execute_graph(), pause_graph(), resume_graph(), stop_graph() methods per contracts/parallel-execution.md
- [X] T065 [US3] Implement advance_step() with isolation guarantee per contracts/parallel-execution.md
- [X] T066 [US3] Implement GraphRegistry for active graph tracking in src/runtime/graph_registry.py per plan.md
- [X] T067 [US3] Implement state isolation enforcement (deep copy validation) per research.md Decision 1
- [X] T068 [US3] Implement ConflictInfo and ConflictHandler per contracts/parallel-execution.md conflict detection section
- [X] T069 [US3] Implement user notification on conflict per spec clarification (optimistic locking with last-write-wins)
- [X] T070 [US3] Add ResourceUsage tracking per contracts/parallel-execution.md resource limits
- [X] T071 [US3] Implement resource warning when approaching limits per edge case: Memory constraints

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently. Parallel execution maintains isolation, no blocking, conflict handling works.

---

## Phase 6: User Story 4 - Custom Seed Input on Fork (Priority: P2)

**Goal**: Allow users to provide custom seed values when creating forks for deterministic control over narrative variation and reproducible outcomes.

**Independent Test**: Fork with known seed, observe generated content, recreate same fork with same seed, verify identical narrative outcomes (graph IDs differ but content identical).

### Tests for User Story 4 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T072 [P] [US4] Unit test for custom seed produces deterministic output in tests/unit/services/test_graph_forker.py per CA-004
- [X] T073 [P] [US4] Unit test for auto-generated seed when no custom seed provided per FR-006
- [X] T074 [US4] Integration test for deterministic reproduction with same seed in tests/integration/test_deterministic_seeds.py per SC-006
- [X] T075 [US4] Integration test for seed scoping (same seed in different graphs produces independent sequences) per edge case: Seed collision

### Implementation for User Story 4

- [X] T076 [US4] Enhance GraphForkRequest validation for customSeed field per contracts/graph-forking.md (min/max length)
- [X] T077 [US4] Implement string-based seed with hash-derived numeric state per research.md Decision 2
- [X] T078 [US4] Implement auto-generation of unique random seed (16 chars alphanumeric) when no custom seed per data-model.md auto-generation section
- [X] T079 [US4] Integrate seed configuration into GraphForker.fork_graph() flow per quickstart.md basic usage examples
- [X] T080 [US4] Implement seed validation in GraphForker.validate_fork_request() per contracts/graph-forking.md error codes
- [X] T081 [US4] Update CLI fork command to accept --seed option per quickstart.md CLI commands section
- [X] T082 [US4] Add seed display in multi-graph view (show seed in graph metadata) per FR-007

**Checkpoint**: All user stories should now be independently functional. Custom seeds work deterministically, auto-generation works, seed scoping prevents collisions.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, final verification

### Documentation & Validation

- [ ] T083 [P] Update quickstart.md with actual CLI commands and verified examples
- [ ] T084 [P] Add docstrings to all public modules, classes, functions per AGENTS.md code style
- [ ] T085 [P] Verify type hints on all function signatures per AGENTS.md

### Testing & Quality

- [ ] T086 [P] Add additional unit tests for edge cases (max graph limit, fork of fork, circular references) per spec.md edge cases
- [ ] T087 Verify fork creation <500ms performance per CA-005
- [ ] T088 Verify graph switch <300ms for 1000 nodes per CA-005
- [ ] T089 Verify multi-graph view <200ms for 50 graphs per CA-005
- [ ] T090 [P] Add unit tests for GraphLineage tree operations (depth calculation, branch ID)

### Performance & Hardening

- [ ] T091 Add coherence validation on all narrative transitions (>0.7 threshold) per CA-001
- [ ] T092 Implement circular reference detection per edge case: Circular references
- [ ] T093 Implement graph limit enforcement (max 50 graphs) with graceful handling per edge case: Maximum graph limit
- [ ] T094 Add structured logging verification for all fork/create/switch/delete operations per SC-009
- [ ] T095 Verify optimistic locking implementation per research.md Decision 6

### Integration Verification

- [ ] T096 Run quickstart.md validation - all examples work as documented
- [ ] T097 Run full integration test suite: `uv run pytest tests/integration/`
- [ ] T098 Run contract test suite: `uv run pytest tests/contract/`
- [ ] T099 Verify ≥80% test coverage on new code per AGENTS.md

**Checkpoint**: Feature complete, all tests passing, performance budgets met, documentation accurate.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
  - T009, T010, T011, T012 (models) can run in parallel
  - T014, T015 (persistence schema) can run in parallel
  - T013 depends on T009, T010 (GraphInstance needs ForkPoint, SeedConfiguration)
  - T016, T017 (store implementations) depend on T014, T015
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order: US1 (P1) → US2 (P1) → US3 (P2) → US4 (P2)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Integrates with US1 (forks created by US1 are viewed in US2), but independently testable
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Uses graphs from US1/US2 but independently testable
- **User Story 4 (P2)**: Can start after US1 complete - Enhances fork creation with seed input, depends on T028 (GraphForker)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD per Constitution)
- Models before services
- Services before CLI commands
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks (T001-T008) marked [P] can run in parallel
- All Foundational model tasks (T009-T012) marked [P] can run in parallel
- All Foundational persistence schema tasks (T014-T015) marked [P] can run in parallel
- All US1 tests (T021-T025) marked [P] can run in parallel
- All US1 models (T026-T027) marked [P] can run in parallel
- All US2 tests (T036-T041) marked [P] can run in parallel
- All US4 tests (T072-T075) marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members once Foundational is complete

---

## Parallel Example: User Story 1 (P1 - MVP)

```bash
# Launch all required tests for User Story 1 together:
Task: "T021 Contract test for GraphForkRequest/GraphForkResponse in tests/contract/test_graph_forking.py"
Task: "T022 Unit test for ForkPoint validation in tests/unit/models/test_fork_point.py"
Task: "T023 Unit test for SeedConfiguration auto-generation in tests/unit/models/test_seed_config.py"
Task: "T024 Integration test for fork isolation in tests/integration/test_fork_isolation.py"
Task: "T025 Integration test for fork immutability in tests/integration/test_fork_isolation.py"

# Launch models for User Story 1 together (after tests written):
Task: "T026 Implement GraphForkRequest Pydantic model in src/models/requests.py"
Task: "T027 Implement GraphForkResponse Pydantic model in src/models/responses.py"

# Then implement service (depends on models):
Task: "T028 Implement GraphForker service with fork_graph() method in src/services/graph_forker.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Fork Graph at Edge)
4. **STOP and VALIDATE**: Test User Story 1 independently
   - Create a fork from an edge
   - Verify new graph created with shared history
   - Verify original graph unaffected
   - Verify fork creation <500ms
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (P1) → Test independently → Deploy/Demo (MVP!)
   - Users can fork graphs at edges
3. Add User Story 2 (P1) → Test independently → Deploy/Demo
   - Users can view and switch between multiple graphs
4. Add User Story 3 (P2) → Test independently → Deploy/Demo
   - Users can execute graphs in parallel
5. Add User Story 4 (P2) → Test independently → Deploy/Demo
   - Users can provide custom seeds for deterministic forks
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (P1 - Fork) + User Story 4 (P2 - Seeds, depends on US1)
   - Developer B: User Story 2 (P1 - View/Switch)
   - Developer C: User Story 3 (P2 - Parallel Execution)
3. Stories complete and integrate independently
4. Phase 7 (Polish) done collaboratively

---

## Task Summary

| Phase | Task Count | Story | Priority |
|-------|-----------|-------|----------|
| Phase 1: Setup | 8 tasks | - | - |
| Phase 2: Foundational | 12 tasks | - | Blocking |
| Phase 3: User Story 1 | 15 tasks | Fork Graph at Edge | P1 (MVP) |
| Phase 4: User Story 2 | 20 tasks | View and Switch | P1 |
| Phase 5: User Story 3 | 16 tasks | Parallel Execution | P2 |
| Phase 6: User Story 4 | 11 tasks | Custom Seed Input | P2 |
| Phase 7: Polish | 17 tasks | - | - |
| **TOTAL** | **99 tasks** | | |

### Parallel Opportunities Identified

- **Setup phase**: 7 of 8 tasks can run in parallel
- **Foundational phase**: 7 of 12 tasks can run in parallel
- **US1 tests**: 4 of 5 test tasks can run in parallel
- **US2 tests**: 5 of 6 test tasks can run in parallel
- **US4 tests**: All 4 test tasks can run in parallel
- **Cross-story parallel**: All 4 user stories can be developed in parallel once Foundational complete

### Independent Test Criteria by Story

- **US1**: Fork creates isolated graph, history immutable, <500ms
- **US2**: Multi-graph view shows all graphs, switch <500ms, filtering works
- **US3**: Parallel execution maintains isolation, no blocking, conflicts detected
- **US4**: Same seed produces identical content, different seeds produce different content

### Suggested MVP Scope

**User Story 1 only (Fork Graph at Edge)**:
- Phases 1-3 complete
- Users can fork at any edge
- Forks are isolated and immutable
- Auto-generated seeds
- Basic CLI commands

This provides immediate value for narrative exploration without requiring the full multi-graph view or parallel execution infrastructure.

---

## Notes

- [P] tasks = different files, no dependencies within the same story phase
- [Story] label maps task to specific user story for traceability (US1, US2, US3, US4)
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD per Constitution CA-004)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Performance budgets: Fork <500ms, Switch <300ms, View <200ms
- Coherence threshold: >0.7 on all narrative transitions
- All operations logged with structured timestamps per SC-009
