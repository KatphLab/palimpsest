# Tasks: TUI Multi-Graph Forking

**Input**: Design documents from `/specs/003-tui-graph-forking/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are REQUIRED. For each user story, write failing tests before implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Verify Python 3.12+ environment and uv dependencies per plan.md
- [x] T002 [P] Ensure existing project structure at src/main.py, src/tui/, src/runtime/, src/models/ exists

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Data Models (All Stories Depend On These)

- [x] T003 [P] Implement GraphSession entity in src/models/graph_session.py
- [x] T004 [P] Implement ForkRequest entity in src/models/fork_request.py
- [x] T005 [P] Implement GraphRegistry entity in src/models/graph_registry.py
- [x] T006 [P] Implement StatusSnapshot entity in src/models/status_snapshot.py
- [x] T007 [P] Implement ForkFromCurrentNodeRequest contract in src/models/requests.py
- [x] T008 [P] Implement GraphSwitchRequest and GraphNavigationDirection in src/models/requests.py
- [x] T009 [P] Implement MultiGraphStatusSnapshot and RunningState in src/models/responses.py
- [x] T010 [P] Implement multi_graph_view models in src/models/multi_graph_view.py

### Runtime Infrastructure

- [x] T011 Implement graph_registry.py in src/runtime/graph_registry.py
- [x] T012 Implement multi_graph_executor.py in src/runtime/multi_graph_executor.py
- [x] T013 Implement session_runtime.py active graph context in src/runtime/session_runtime.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Fork From Active Node in TUI (Priority: P1) 🎯 MVP

**Goal**: Allow users to fork from the currently focused node with the `f` hotkey, enter a seed, and create a new graph that becomes active while preserving source graph state.

**Independent Test**: Can be fully tested by opening the TUI, selecting a node, pressing `f`, entering a seed, and confirming a new graph becomes active while the source graph remains unchanged.

### Tests for User Story 1 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T014 [P] [US1] Contract test for ForkFromCurrentNodeRequest in tests/contract/test_fork_request.py
- [x] T015 [P] [US1] Unit test for `f` keybinding initiating fork flow in tests/unit/test_tui_app.py
- [x] T016 [P] [US1] Unit test for fork cancel behavior in tests/unit/test_tui_app.py
- [x] T017 [P] [US1] Integration test for fork-from-current-node flow in tests/integration/test_fork_flow.py
- [x] T018 [P] [US1] Integration test for fork confirmation creates new active graph in tests/integration/test_fork_flow.py

### Implementation for User Story 1

- [x] T019 [US1] Add `f` keybinding in src/tui/app.py to initiate fork flow
- [x] T020 [US1] Create fork seed prompt screen in src/tui/screens.py
- [x] T021 [US1] Implement fork confirmation handler in src/tui/app.py
- [x] T022 [US1] Implement fork cancel handler in src/tui/app.py
- [x] T023 [US1] Create graph forking service in src/services/graph_forker.py
- [x] T024 [US1] Integrate forking with graph_registry.py to append new graph
- [x] T025 [US1] Update session_runtime.py to set forked graph as active
- [x] T026 [US1] Add validation for current_node_id exists before fork in src/tui/app.py
- [x] T027 [US1] Add error handling for fork flow with no current node in src/tui/app.py
- [x] T028 [US1] Add logging for fork operations in src/runtime/session_runtime.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Navigate and Track Multiple Graphs (Priority: P1)

**Goal**: Allow users to see which graph they are on (position/total) in the status bar and switch between graphs using `Tab` and `Shift+Tab`.

**Independent Test**: Can be fully tested by creating multiple graphs, switching with `Tab` and `Shift+Tab`, and verifying the status bar shows "current graph number / total graphs" accurately after each switch.

### Tests for User Story 2 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T029 [P] [US2] Contract test for GraphSwitchRequest in tests/contract/test_graph_switch.py
- [x] T030 [P] [US2] Contract test for MultiGraphStatusSnapshot in tests/contract/test_multi_graph_view.py
- [x] T031 [P] [US2] Unit test for `Tab` keybinding switching to next graph in tests/unit/test_tui_app.py
- [x] T032 [P] [US2] Unit test for `Shift+Tab` keybinding switching to previous graph in tests/unit/test_tui_app.py
- [x] T033 [P] [US2] Unit test for status bar rendering active_position/total_graphs in tests/unit/test_tui_widgets.py
- [x] T034 [P] [US2] Unit test for graph cycling wrapping at boundaries in tests/unit/services/test_graph_switcher.py
- [x] T035 [P] [US2] Integration test for multi-graph view integrity in tests/integration/test_multi_graph_view.py

### Implementation for User Story 2

- [x] T036 [US2] Add `Tab` keybinding in src/tui/app.py for next graph
- [x] T037 [US2] Add `Shift+Tab` keybinding in src/tui/app.py for previous graph
- [x] T038 [US2] Implement graph switcher service in src/services/graph_switcher.py
- [x] T039 [US2] Update graph_registry.py with cyclic navigation logic
- [x] T040 [US2] Create status/footer widget in src/tui/widgets.py for position/total display
- [x] T041 [US2] Update story_projection.py to reflect active graph changes
- [x] T042 [US2] Implement status bar update in same interaction cycle as graph switch in src/tui/app.py
- [x] T043 [US2] Add handling for single graph case (Tab/Shift+Tab no-op) in src/tui/app.py
- [x] T044 [US2] Add handling for dynamic graph lifecycle changes in src/runtime/session_runtime.py
- [x] T045 [US2] Add logging for graph switch operations in src/runtime/session_runtime.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Run Graphs Concurrently Off-Screen (Priority: P2)

**Goal**: Allow non-active graphs to keep running while user works on another graph, with status bar showing only the active graph's running state.

**Independent Test**: Can be fully tested by running two graphs, switching to one graph, waiting for background activity, then switching back and verifying the previously inactive graph advanced independently.

### Tests for User Story 3 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T046 [P] [US3] Unit test for active-only running state in status snapshot in tests/unit/test_tui_widgets.py
- [x] T047 [P] [US3] Integration test for background graph progression in tests/integration/test_parallel_execution.py
- [x] T048 [P] [US3] Integration test for status bar active-only running state display in tests/integration/test_parallel_execution.py
- [x] T049 [P] [US3] Integration test for inactive graph advancement while off-screen in tests/integration/test_parallel_execution.py

### Implementation for User Story 3

- [ ] T050 [US3] Update multi_graph_executor.py to continue execution for all graphs regardless of focus
- [ ] T051 [US3] Implement active graph running state extraction in src/runtime/session_runtime.py
- [ ] T052 [US3] Update status widget to render only active graph running state in src/tui/widgets.py
- [ ] T053 [US3] Add background state isolation to prevent status leakage in src/runtime/session_runtime.py
- [ ] T054 [US3] Verify latency targets in integration tests (switch <300ms, fork <1s per CA-005)
- [ ] T055 [US3] Add timing instrumentation to graph switch operations in src/runtime/session_runtime.py
- [ ] T056 [US3] Add timing instrumentation to fork operations in src/runtime/session_runtime.py

**Checkpoint**: All user stories 1-3 should now be independently functional

---

## Phase 6: User Story 4 - Enforce TUI as Sole Entry Point (Priority: P2)

**Goal**: Remove or disable all non-TUI entry points so that the TUI is the only supported way to start and interact with the system.

**Independent Test**: Can be fully tested by attempting to launch the application through previously available alternate entry paths and verifying only the TUI entry path remains available.

### Tests for User Story 4 (REQUIRED) ✅

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T057 [P] [US4] Unit test proving non-TUI entry paths are unavailable in tests/unit/test_tui_app.py
- [ ] T058 [P] [US4] Unit test proving TUI entry path opens successfully in tests/unit/test_tui_app.py
- [ ] T059 [P] [US4] Integration test for TUI-only startup workflow in tests/integration/test_multi_graph_view.py

### Implementation for User Story 4

- [ ] T060 [US4] Remove or disable src/cli/main.py alternate entrypoint
- [ ] T061 [US4] Update src/main.py to ensure it is the sole supported startup path
- [ ] T062 [US4] Verify TUI opens all core workflows on startup
- [ ] T063 [US4] Update documentation to reflect TUI-only entrypoint
- [ ] T064 [US4] Add startup validation that TUI is the entry path in src/main.py

**Checkpoint**: All user stories should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

### Documentation

- [ ] T065 [P] Update README.md with TUI-only entrypoint instructions
- [ ] T066 [P] Update quickstart.md with multi-graph workflow examples
- [ ] T067 [P] Document keybindings (`f`, `Tab`, `Shift+Tab`) in docs/

### Code Quality & Testing

- [ ] T068 [P] Add additional unit tests for edge cases in tests/unit/test_tui_app.py
- [ ] T069 [P] Add unit tests for graph_registry edge cases in tests/unit/services/
- [ ] T070 [P] Add integration tests for 10 concurrent graphs scenario per SC-003
- [ ] T071 Run full test suite: uv run pytest tests/ -v
- [ ] T072 Verify test coverage >=80% for new code

### Performance & Budget

- [ ] T073 Verify graph switch feedback <300ms with 10 concurrent graphs per CA-005
- [ ] T074 Verify fork confirmation <1s under normal conditions per CA-005
- [ ] T075 [P] Add performance regression tests for latency thresholds

### Safety & Observability

- [ ] T076 [P] Verify fork/switch actions emit to command/runtime event logs
- [ ] T077 Verify source graph isolation at fork boundary per CA-002
- [ ] T078 Verify active graph uniqueness invariant in runtime
- [ ] T079 Verify coherence scoring hooks for fork narrative continuity per CA-001

### Quickstart Validation

- [ ] T080 Execute quickstart.md steps 1-7 and verify all pass
- [ ] T081 Validate all acceptance scenarios from spec.md execute correctly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1 - Fork)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1 - Navigate)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P2 - Concurrent)**: Can start after Foundational (Phase 2) - Builds on US1/US2 for multi-graph scenarios
- **User Story 4 (P2 - Entrypoint)**: Can start after Foundational (Phase 2) - Independent infrastructure change

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before TUI bindings
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1 (Fork)

```bash
# Launch all required tests for User Story 1 together:
Task: "Contract test for ForkFromCurrentNodeRequest in tests/contract/test_fork_request.py"
Task: "Unit test for `f` keybinding initiating fork flow in tests/unit/test_tui_app.py"
Task: "Unit test for fork cancel behavior in tests/unit/test_tui_app.py"
Task: "Integration test for fork-from-current-node flow in tests/integration/test_fork_flow.py"

# Launch all foundational models together (already in Phase 2, but illustrative):
Task: "Implement ForkRequest entity in src/models/fork_request.py"
Task: "Implement ForkFromCurrentNodeRequest contract in src/models/requests.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Fork From Active Node)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (Fork) → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 (Navigate) → Test independently → Deploy/Demo
4. Add User Story 3 (Concurrent) → Test independently → Deploy/Demo
5. Add User Story 4 (Entrypoint) → Test independently → Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Fork)
   - Developer B: User Story 2 (Navigate)
   - Developer C: User Story 3 (Concurrent)
   - Developer D: User Story 4 (Entrypoint)
3. Stories complete and integrate independently

---

## Summary

| Phase | User Story                     | Priority | Task Count | Key Deliverable                           |
| ----- | ------------------------------ | -------- | ---------- | ----------------------------------------- |
| 1     | Setup                          | -        | 2          | Environment verified                      |
| 2     | Foundational                   | -        | 12         | Data models + runtime infra               |
| 3     | US1 - Fork From Active Node    | P1       | 15         | `f` hotkey fork flow                      |
| 4     | US2 - Navigate Multiple Graphs | P1       | 17         | `Tab`/`Shift+Tab` + status bar            |
| 5     | US3 - Concurrent Execution     | P2       | 11         | Background execution + active-only status |
| 6     | US4 - TUI-Only Entrypoint      | P2       | 8          | Remove alternate entrypoints              |
| 7     | Polish                         | -        | 17         | Docs, tests, performance, safety          |

**Total Tasks**: 82
**Parallel Opportunities**: All [P] marked tasks across all phases
**MVP Scope**: User Story 1 (Fork) alone delivers core value
**Suggested First Steps**: T001-T013 (Setup + Foundational), then T014-T028 (US1 tests + implementation)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
