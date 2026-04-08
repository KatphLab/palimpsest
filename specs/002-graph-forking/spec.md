# Feature Specification: Graph Forking with Multi-Graph View

**Feature Branch**: `002-graph-forking`
**Created**: 2026-04-08
**Status**: Draft
**Input**: User description: "I want to work on integrating forking of the graph at an edge and integrate a view to see the different graphs and switch between them. I should be able to have multiple graphs running in parallel. when a new fork is created, I want to be able to add my own seed."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fork Graph at Edge (Priority: P1)

As a narrative designer, I want to create a fork at any edge in the graph so that I can explore multiple narrative branches from a single decision point without destroying the original path.

**Why this priority**: Forking is the core capability that enables non-linear narrative exploration. Without it, users are constrained to a single linear path.

**Independent Test**: Can be fully tested by selecting any edge in an active graph, invoking the fork action, and verifying that a new parallel graph instance is created sharing the history up to that edge.

**Acceptance Scenarios**:

1. **Given** an active narrative graph with multiple edges, **When** I select a specific edge and invoke the fork command, **Then** a new graph instance is created that shares the node/edge history up to that point but branches with a new path from the selected edge, with progress shown via a status bar indicator.

2. **Given** a graph with an existing fork, **When** I create another fork from a different edge, **Then** both forked graphs remain independent and can be accessed separately.

3. **Given** I have initiated a fork operation, **When** I provide a custom seed value, **Then** the new forked graph uses that seed for its narrative generation while the original graph continues unaffected.

---

### User Story 2 - View and Switch Between Graphs (Priority: P1)

As a narrative designer, I want to see a visual overview of all my active graph instances and switch between them so that I can manage multiple parallel narrative threads efficiently.

**Why this priority**: Without visibility into parallel graphs, users lose track of their narrative branches, making the forking feature impractical for real use.

**Independent Test**: Can be fully tested by creating multiple forks, opening the multi-graph view, and verifying all graphs are visible with metadata; then selecting any graph to switch to it.

**Acceptance Scenarios**:

1. **Given** I have multiple active graph instances (original and forks), **When** I open the graph browser/manager view, **Then** I see a list or visualization of all graphs with distinguishing information (creation time, fork point, current state summary).

2. **Given** I am viewing the multi-graph view, **When** I select a specific graph instance, **Then** the system displays a progress indicator and switches to that graph's current state within 500ms, allowing continued interaction.

3. **Given** I have many graph instances, **When** I browse the multi-graph view, **Then** I can filter or search graphs by attributes like creation time, fork source, or custom labels I have assigned.

---

### User Story 3 - Parallel Graph Execution (Priority: P2)

As a narrative designer, I want multiple graph instances to run independently in parallel so that I can explore different narrative outcomes simultaneously without one blocking another.

**Why this priority**: Parallel execution enables true branching exploration where users can advance multiple storylines concurrently, which is essential for complex narrative design workflows.

**Independent Test**: Can be fully tested by creating two forks, advancing each graph independently, and verifying that state changes in one do not affect the other and both progress simultaneously.

**Acceptance Scenarios**:

1. **Given** I have two active graph forks, **When** I advance the narrative in Graph A by several steps, **Then** Graph B remains at its previous state and is unaffected by Graph A's progression.

2. **Given** I have multiple graphs running, **When** I switch between them rapidly, **Then** each graph maintains its own execution state, node positions, and active edges independently.

3. **Given** I am actively working with one graph, **When** background processing occurs on other graphs (e.g., AI generation), **Then** it does not block or slow down my current graph interaction.

---

### User Story 4 - Custom Seed Input on Fork (Priority: P2)

As a narrative designer, I want to provide my own seed value when creating a fork so that I can have deterministic control over the narrative variation and reproduce specific outcomes.

**Why this priority**: Custom seeds enable reproducible narrative experiments and allow users to intentionally explore specific narrative spaces rather than relying solely on randomness.

**Independent Test**: Can be fully tested by forking with a known seed, observing generated content, recreating the same fork with the same seed, and verifying identical narrative outcomes.

**Acceptance Scenarios**:

1. **Given** I am creating a fork from an edge, **When** the fork dialog appears, **Then** I can optionally enter a custom seed string or number before confirming.

2. **Given** I have forked a graph with a specific seed, **When** I create another fork from the same edge using the same seed, **Then** the narrative generation follows the same path (deterministic behavior).

3. **Given** I do not provide a custom seed, **When** a fork is created, **Then** the system automatically generates a unique random seed to ensure variation.

---

### Edge Cases

- **Maximum graph limit**: What happens when the system reaches a maximum number of parallel graphs? The system should gracefully handle this by either prompting to archive/delete old graphs or implementing automatic cleanup of inactive graphs.

- **Fork of a fork**: Can a forked graph be forked again? Yes, and the lineage should be tracked to maintain a tree structure of graph relationships.

- **Circular references**: How are circular narrative paths handled when forking? The system should detect and prevent infinite loops or circular dependencies when forking edges that could create cycles.

- **Memory constraints**: What happens if parallel graphs consume excessive memory? The system should implement resource limits and provide warnings when approaching thresholds.

- **Seed collision**: How are duplicate seeds across different forks handled? Seeds should be scoped per-fork, so identical seeds in different graphs produce independent deterministic sequences.

- **Graph deletion**: What happens when a parent graph is deleted but its forks remain? Forks should become independent roots, preserving their full history and not breaking when parent graphs are removed.

- **Concurrent access conflicts**: When switching rapidly between graphs or when background operations overlap with user edits, the system uses optimistic locking with last-write-wins. Users are notified if their changes conflict with a background update and can choose to retry or discard.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to create a fork at any edge in an active graph, creating a new independent graph instance that shares the node/edge history up to the fork point.

- **FR-002**: System MUST maintain complete isolation between forked graph instances, ensuring that state changes in one graph do not propagate to others.

- **FR-003**: System MUST provide a multi-graph view that displays all active graph instances with distinguishing metadata (creation timestamp, fork source, current node count, custom labels).

- **FR-004**: Users MUST be able to switch between any active graph instance from the multi-graph view, with the system loading the selected graph's complete state.

- **FR-005**: When creating a fork, System MUST provide an interface for users to optionally input a custom seed value that controls the narrative generation determinism for that fork.

- **FR-006**: System MUST generate a unique random seed automatically when the user does not provide a custom seed during fork creation.

- **FR-007**: System MUST track and display graph lineage/fork ancestry to help users understand the relationship between original graphs and their forks.

- **FR-008**: System MUST support parallel execution of multiple graphs without blocking or interference between instances.

- **FR-009**: System MUST allow users to delete/archive individual graph instances without affecting sibling or parent fork instances.

- **FR-010**: System MUST persist all active graph states so that parallel graphs survive session restarts and can be resumed independently.

### Constitution Alignment *(mandatory)*

- **CA-001 Coherence**: Each forked graph must maintain internal narrative coherence. The acceptance threshold requires that narrative transitions between connected nodes in any fork must score above 0.7 on a coherence metric measuring thematic and logical continuity.

- **CA-002 Mutation Safety**: Fork operations must be atomic and preserve the integrity of the original graph. Once created, a fork's history up to the fork point must be immutable. Graph mutations (add/remove nodes/edges) must be scoped to the specific graph instance only.

- **CA-003 Typed Contracts**:
  - GraphForkRequest: `{ sourceGraphId: string, forkEdgeId: string, customSeed?: string, label?: string }`
  - GraphForkResponse: `{ forkedGraphId: string, forkPoint: EdgeReference, seed: string, creationTime: timestamp }`
  - MultiGraphView: `{ graphs: GraphSummary[], activeGraphId: string | null }`
  - GraphSwitchRequest: `{ targetGraphId: string }`

- **CA-004 Test-First Verification**:
  - Test that fork creates isolated graph instance
  - Test that custom seed produces deterministic output
  - Test that multi-graph view returns all active graphs
  - Test that graph switch loads correct state
  - Test that parallel execution maintains isolation

- **CA-005 Budget Compliance**: Fork creation must complete within 500ms. Multi-graph view rendering must complete within 200ms for up to 50 graphs. Graph switch operation must complete within 300ms.

### Key Entities *(include if feature involves data)*

- **GraphInstance**: Represents a single narrative graph with its own nodes, edges, and state. Contains a unique identifier, creation metadata, fork ancestry reference, current seed, and node/edge collections.

- **ForkPoint**: Represents the location where a fork was created. Contains the source graph ID, the specific edge ID where the fork occurred, the timestamp, and an optional user-provided label.

- **GraphLineage**: Tracks the hierarchical relationship between graphs in a fork tree. Contains parent-child references, depth level, and branch identifiers to maintain ancestry information.

- **SeedConfiguration**: Stores seed settings for a graph instance. Contains the seed value (custom or auto-generated), algorithm identifier, and deterministic mode flag.

- **MultiGraphViewState**: Represents the user's current browsing context in the multi-graph view. Contains the list of visible graphs, active filters, selected graph ID, and view preferences.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create a fork from any edge in under 3 clicks/keystrokes.

- **SC-002**: The multi-graph view displays up to 50 active graphs with metadata in under 1 second.

- **SC-003**: Switching between graph instances completes in under 500ms for graphs with up to 1000 nodes.

- **SC-004**: 95% of fork operations successfully create isolated graph instances with no data leakage between graphs.

- **SC-005**: Users can provide custom seeds in 100% of fork operations when desired.

- **SC-006**: Deterministic reproduction: Using the same seed on the same fork point produces identical narrative outcomes 100% of the time.

- **SC-007**: Users can simultaneously work with up to 10 active graph instances without performance degradation (defined as <100ms latency increase per operation).

- **SC-008**: All graph states persist across sessions with 100% accuracy - no data loss when restarting the application.

- **SC-009**: All fork, create, switch, and delete operations are logged with structured timestamps for debugging and performance validation.

## Clarifications

### Session 2026-04-08

- **Q:** What is the security model and authentication/authorization scope for graph instances? → **A:** Single-user local application with file-based persistence - no multi-user auth required (Option A).

- **Q:** How should concurrent access across forks be handled (conflict resolution)? → **A:** Optimistic locking with last-write-wins and user notification on conflict (Option B).

- **Q:** What telemetry and observability requirements exist for multi-graph operations? → **A:** Basic structured logging only - log fork/create/switch/delete operations with timestamps (Option A).

- **Q:** Can graphs be exported and imported for backup/sharing? → **A:** No export/import - graphs are transient and recreated from scratch (Option C).

- **Q:** How should async operations (fork creation, graph switching) indicate loading/progress in the UI? → **A:** Minimal loading states - progress bar in status area for async operations (Option A).

## Assumptions

- Users are comfortable with branching narrative concepts and understand that forking creates parallel timeline scenarios.

- The system has sufficient storage to maintain multiple parallel graph states; storage quotas are managed outside this feature scope.

- Performance requirements assume graphs with up to 10,000 nodes; larger graphs may have degraded but functional performance.

- The existing graph execution engine can be extended to support multiple concurrent instances without major architectural changes.

- Users will primarily work with 1-10 parallel graphs simultaneously; the UI is optimized for this scale though it supports larger numbers.

- Custom seeds are provided as strings or numbers; complex seed objects are out of scope for this feature version.

- **Security Model**: This is a single-user local application with file-based persistence; no multi-user authentication or authorization required. Graph isolation is enforced through in-memory and file-level separation only.

- **Data Portability**: Graphs are transient and cannot be exported or imported. Persistence is limited to session-local storage; users recreate graphs from scratch when needed.
