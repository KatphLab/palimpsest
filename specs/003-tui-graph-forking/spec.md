# Feature Specification: TUI Multi-Graph Forking

**Feature Branch**: `003-tui-graph-forking`
**Created**: 2026-04-08
**Status**: Draft
**Input**: User description: "integrate graph forking into tui and keep tui as the only entrypoint to the application. remove other entrypoints. add `f` hotkey to fork from the current node, then user can enter the seed node and continue on the new graph. user should see graph no / total graph count in the status bar and should be able to switch using tab and shift tab between graphs. The graphs should be allowed to keep running even when they are in not the active one. the running status should show the status of the active graph only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fork From Active Node in TUI (Priority: P1)

As a narrative designer using the terminal interface, I want to fork from the currently focused node with a single hotkey and set a seed for the new fork so I can branch the story quickly without leaving the TUI flow.

**Why this priority**: Forking from the current node is the primary user action requested and unlocks all multi-graph exploration value.

**Independent Test**: Can be fully tested by opening the TUI, selecting a node, pressing `f`, entering a seed, and confirming a new graph becomes active while the source graph remains unchanged.

**Acceptance Scenarios**:

1. **Given** a graph is open and a current node is selected, **When** the user presses `f`, **Then** the system initiates a fork flow from that current node.
2. **Given** the fork flow is active, **When** the user enters a seed and confirms, **Then** a new graph is created using that seed and opened as the active graph.
3. **Given** the fork flow is active, **When** the user cancels before confirming, **Then** no new graph is created and the current graph remains active.

---

### User Story 2 - Navigate and Track Multiple Graphs (Priority: P1)

As a narrative designer managing parallel branches, I want to see which graph I am on and quickly switch with keyboard shortcuts so I can compare and steer multiple narrative paths efficiently.

**Why this priority**: Without clear graph indexing and switching controls, users cannot effectively operate multiple graphs in a TUI-only workflow.

**Independent Test**: Can be fully tested by creating multiple graphs, switching with `Tab` and `Shift+Tab`, and verifying the status bar shows "current graph number / total graphs" accurately after each switch.

**Acceptance Scenarios**:

1. **Given** two or more graphs exist, **When** the user presses `Tab`, **Then** focus switches to the next graph in the cycle.
2. **Given** two or more graphs exist, **When** the user presses `Shift+Tab`, **Then** focus switches to the previous graph in the cycle.
3. **Given** any graph is active, **When** the status bar is rendered, **Then** it displays the active graph position and total graph count.

---

### User Story 3 - Run Graphs Concurrently Off-Screen (Priority: P2)

As a narrative designer, I want non-active graphs to keep running while I work on another graph so that exploration progress continues in parallel.

**Why this priority**: Background progression is required to realize the value of parallel graph branching and avoids forcing users to babysit each graph one at a time.

**Independent Test**: Can be fully tested by running two graphs, switching to one graph, waiting for background activity, then switching back and verifying the previously inactive graph advanced independently.

**Acceptance Scenarios**:

1. **Given** multiple graphs are running, **When** the user switches to another graph, **Then** previously active graphs continue progressing while not focused.
2. **Given** one graph is active and others are inactive, **When** running status is shown, **Then** only the active graph's running status is displayed in the status area.
3. **Given** the active graph is idle and a background graph is running, **When** status is displayed, **Then** the active graph appears idle and no background graph status overrides it.

---

### User Story 4 - Enforce TUI as Sole Entry Point (Priority: P2)

As an operator of the application, I want the TUI to be the only supported way to start and interact with the system so usage is consistent and all workflows remain in one interface.

**Why this priority**: Removing alternate entry points reduces confusion, avoids divergent behavior, and aligns operation with the requested single-interface model.

**Independent Test**: Can be fully tested by attempting to launch the application through previously available alternate entry paths and verifying only the TUI entry path remains available.

**Acceptance Scenarios**:

1. **Given** a user attempts to start the app through a removed entry path, **When** launch is attempted, **Then** that path is unavailable to start application workflows.
2. **Given** a user starts the app through the supported path, **When** startup completes, **Then** the TUI opens and all core workflows remain accessible there.

---

### Edge Cases

- If the user presses `f` when no current node is available, the system informs the user and does not start fork creation.
- If the seed input is left blank, the system still creates the fork using the default seed behavior defined by current graph rules.
- If there is only one graph, `Tab` and `Shift+Tab` do not error and keep focus on the same graph.
- If a graph is removed or completes while cycling, graph numbering and total count update immediately and remain accurate.
- If multiple graphs finish or fail while another graph is active, active-graph running status remains tied only to the currently focused graph.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a single supported application entry point through the TUI.
- **FR-002**: System MUST remove or disable all non-TUI entry points from normal application startup and interaction paths.
- **FR-003**: System MUST allow the user to initiate graph forking from the current node via the `f` hotkey.
- **FR-004**: After fork initiation, System MUST prompt the user for a seed before creating the new graph, with an option to cancel.
- **FR-005**: Upon confirmed fork creation, System MUST create a new graph derived from the current node context and set the new graph as active.
- **FR-006**: System MUST preserve source graph state when a fork is created so no source-graph mutation occurs beyond normal progression.
- **FR-007**: System MUST display active graph index and total graph count in the status bar at all times during normal operation.
- **FR-008**: Users MUST be able to switch to the next graph using `Tab` and to the previous graph using `Shift+Tab`.
- **FR-009**: System MUST allow all graphs to continue execution regardless of whether they are currently active.
- **FR-010**: System MUST show running status for the active graph only, even when non-active graphs are running.
- **FR-011**: Graph switching MUST update active graph context and status bar information in the same interaction cycle so users see immediate feedback.

### Constitution Alignment *(mandatory)*

- **CA-001 Coherence**: Forked graphs must retain narrative continuity from the selected current node; at least 95% of sampled forks should be judged by acceptance tests as logically continuing the selected context.
- **CA-002 Mutation Safety**: Fork creation must preserve source graph history and protect graph boundaries so actions in one graph do not directly mutate another graph's state.
- **CA-003 Typed Contracts**:
  - ForkFromCurrentNodeRequest: contains active graph identifier, current node identifier, and user-provided seed value.
  - GraphSwitchRequest: contains target graph identifier and navigation direction (next or previous).
  - MultiGraphStatusSnapshot: contains active graph position, total graph count, and active graph running state.
- **CA-004 Test-First Verification**:
  - A failing test proving `f` from current node starts fork flow and requires seed confirmation.
  - A failing test proving `Tab` and `Shift+Tab` switch active graph order correctly.
  - A failing test proving inactive graphs continue progressing while not focused.
  - A failing test proving status bar shows graph position/total and active-graph-only running status.
  - A failing test proving non-TUI entry paths can no longer start the application.
- **CA-005 Budget Compliance**: Graph switch feedback should appear within 300 ms in normal interactive use with up to 10 concurrently running graphs; fork confirmation should complete within 1 second in normal conditions.

### Key Entities *(include if feature involves data)*

- **Graph Session**: Represents one independently running narrative graph, including identity, active/inactive focus state, current node, and execution state.
- **Fork Request**: Represents a user-triggered request to branch from the active graph's current node, including proposed seed and confirmation state.
- **Graph Registry**: Represents the ordered collection of graphs available in the TUI, including active position and total count.
- **Status Snapshot**: Represents the information rendered in the TUI status bar for active graph number, total graph count, and active graph running state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of observed production start workflows begin from the TUI entry path, with no alternate entry path available.
- **SC-002**: In usability testing, at least 95% of users can fork from the current node and provide a seed in under 15 seconds without external guidance.
- **SC-003**: In scenario tests with 10 concurrent graphs, graph index/total display remains correct through 100% of switch operations.
- **SC-004**: In scenario tests with 10 concurrent graphs, `Tab` and `Shift+Tab` navigation succeeds on first keypress in at least 99% of switch attempts.
- **SC-005**: In parallel-run tests, non-active graphs continue progressing in at least 99% of observation windows while another graph is active.
- **SC-006**: In status validation tests, active-graph running status is accurate in at least 99% of sampled status updates and is never replaced by background graph status.

## Assumptions

- Users operate the product through an interactive terminal session and rely on keyboard-first controls.
- Existing graph execution behavior remains valid; this feature adds orchestration and visibility for multiple graph sessions.
- Seed entry accepts the same value formats already supported by current narrative generation rules.
- Graph switching order follows the existing graph list ordering used by the application.
- Keeping background graphs running is constrained by current runtime resource limits; no new scaling tier is introduced in this feature.
