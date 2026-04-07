# Feature Specification: Terminal Self-Editing Narrative MVP

**Feature Branch**: `001-terminal-hypergraph-mvp`
**Created**: 2026-04-06
**Spec Version**: 1.2.0
**Status**: Draft
**Input**: User description: `@docs/prd.md`

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Seed and Step Through Narrative Growth (Priority: P1)

As a narrative researcher, I can enter a short story seed in the terminal and step the simulation cycle-by-cycle while the story-flow panel updates.

**Why this priority**: This is the core value of the product; without seed-to-story growth from a seed, no other workflow is meaningful.

**Independent Test**: This can be fully tested by starting a new session, submitting one seed, pressing continue to advance cycles, and confirming the panel reflects ordered story growth.

**Acceptance Scenarios**:

1. **Given** a user has opened the terminal runtime, **When** they submit a valid seed, **Then** the first scene appears within 2 seconds and the session enters active simulation.
2. **Given** an active simulation, **When** the user triggers the continue control, **Then** the runtime advances exactly one cycle and the panel refresh reflects the updated narrative flow.
3. **Given** an active simulation, **When** the user pauses and resumes, **Then** progression halts and restarts without losing current session state.

---

### User Story 2 - Intervene in Narrative Topology (Priority: P2)

As a speculative modeler, I can protect specific narrative links and fork an active run so I can compare alternate evolutions safely.

**Why this priority**: Controlled intervention enables meaningful experimentation and comparison while preserving autonomous behavior.

**Independent Test**: This can be fully tested by locking a selected relationship, triggering mutation activity, and creating an independent fork that continues separately.

**Acceptance Scenarios**:

1. **Given** a session with at least one edge, **When** the user locks that edge, **Then** the edge remains intact during subsequent mutation cycles.
2. **Given** a running session, **When** the user creates a fork, **Then** a new independent session is created with its own session identifier.
3. **Given** an original session and a forked session, **When** the user continues running both, **Then** updates in one session do not alter the other.
4. **Given** a running session, **When** autonomous mutation is evaluating a cycle, **Then** at most one node is activated and at most one mutation is proposed and resolved for that cycle.
5. **Given** a running session, **When** autonomous mutation evaluates a cycle, **Then** mutation action selection is decided by an LLM using narrative context (including at minimum the last two scenes and graph topology counts).

---

### User Story 3 - Inspect Entropy and Mutation Decisions (Priority: P3)

As a narrative researcher, I can monitor entropy hotspots and mutation decisions so I can understand why the story topology changes over time.

**Why this priority**: Interpretability improves trust and allows users to evaluate narrative quality and intervention impact.

**Independent Test**: This can be fully tested by running a session until mutations occur, inspecting node-level details, and exporting the current state.

**Acceptance Scenarios**:

1. **Given** an active session, **When** the user views the monitoring surface, **Then** each visible node shows an entropy score and drift category.
2. **Given** recent mutations exist, **When** the user inspects the event stream, **Then** events appear in chronological order with actor and target identifiers.
3. **Given** an active session, **When** the user exports the graph snapshot, **Then** a complete session graph artifact is produced for offline analysis.
4. **Given** an accepted `add_node` mutation, **When** the mutation is applied, **Then** the runtime generates scene text immediately for the created node in the same mutation cycle.
5. **Given** autonomous mutation decisions occur, **When** the user observes runtime output, **Then** decision source, action, confidence, and reasoning are emitted to both console and file logs.

---

### Edge Cases

- What happens if the user submits an empty seed or a seed longer than 280 characters?
- How does the system behave if all active nodes vote to terminate at nearly the same time?
- What happens if the mutation rate exceeds allowed thresholds during a short time window?
- How does the system handle user commands that reference missing node or edge identifiers?
- What happens if an export path is invalid or not writable?

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The system MUST allow users to start a session by submitting a seed up to 280 characters.
- **FR-002**: The system MUST create the initial scene representation within 2 seconds of valid seed submission.
- **FR-003**: The system MUST provide an explicit continue control that advances exactly one session cycle and refreshes the active-session panel.
- **FR-004**: The system MUST allow users to pause and resume simulation without losing current session state.
- **FR-005**: Users MUST be able to lock and unlock narrative relationships during an active session.
- **FR-006**: The system MUST prevent removal of locked relationships during autonomous mutation handling.
- **FR-007**: Users MUST be able to fork an active session into a new independent in-memory session.
- **FR-008**: The system MUST expose per-node entropy and drift information in the terminal monitoring view.
- **FR-009**: The system MUST provide chronological mutation logs including actor and target identifiers.
- **FR-010**: Users MUST be able to inspect details of a specific node during an active session.
- **FR-011**: Users MUST be able to export the current narrative graph state as a structured JSON artifact.
- **FR-012**: The system MUST enforce mutation safety constraints, including immutable seed node protection and mutation cooldown guardrails.
- **FR-013**: The system MUST trigger global consistency checks at regular intervals and during mutation bursts.
- **FR-014**: The system MUST end a session when termination voting exceeds `TERMINATION_MAJORITY_THRESHOLD` (strictly greater than half of active nodes) and produce a final session summary.
- **FR-015**: The system MUST keep per-session operating cost within the configured budget target and surface budget breach alerts during runtime.
- **FR-016**: The system MUST execute autonomous mutation decisions through a dedicated mutation-proposer workflow separate from scene-generation logic.
- **FR-017**: The system MUST have the LLM select the single node activation candidate for each mutation cycle.
- **FR-018**: The system MUST resolve at most one autonomous mutation per cycle (propose -> safety filter -> applied/rejected/cooled_down terminal outcome).
- **FR-019**: The system MUST generate scene content immediately when an `add_node` mutation is accepted.
- **FR-020**: The system MUST interpret `prune_branch` as removal of an entire targeted subgraph while preserving seed-protected and otherwise protected graph state.
- **FR-021**: The TUI active-session panel MUST render deterministic narrative projection sections for seed, ordered story flow, and detached scenes.
- **FR-022**: The active-session panel MUST support overflow scrolling without forced auto-scroll jumps during refresh.
- **FR-023**: The mutation-action selection stage MUST pass narrative context to the LLM that includes, at minimum, the last two scene texts, node count, edge count, branch count, and active candidate identifier.
- **FR-024**: The system MUST have the LLM decide whether to expand, prune, rewrite, or skip mutation actions using narrative interestingness versus boredom heuristics.
- **FR-025**: The system MUST fall back to a deterministic proposer when the LLM action-decision call fails, times out, or returns invalid structured output.
- **FR-026**: The system MUST log mutation-decision telemetry (decision source, action, confidence, reasoning, and proposal id) to both console and rotating file sinks.

### Constitution Alignment _(mandatory)_

- **CA-001 Coherence**: The feature MUST preserve narrative coherence through continuous local scoring and periodic global checks, with a target global coherence score of at least 0.80 during a 30-minute run.
- **CA-002 Mutation Safety**: The feature MUST enforce bounded mutation behavior: LLM-driven single-node activation per cycle, at most one mutation resolved per cycle, no deletion of protected seed state, no removal of locked relationships, and cooldown behavior during mutation bursts.
- **CA-003 Typed Contracts**: The feature MUST define and validate structured contracts for session state, node state, edge state, mutation decisions, entropy evaluations, and event records; malformed outputs MUST be rejected or safely downgraded.
- **CA-004 Test-First Verification**: The feature MUST define failing acceptance tests before implementation for seed flow, pause/resume controls, lock/fork behaviors, mutation logging, entropy visibility, termination voting, and budget tracking outcomes.
- **CA-005 Budget Compliance**: The feature MUST achieve entropy-breach-to-mutation handling within 5 seconds and keep expected session cost below $5 while surfacing alerts when budget limits are exceeded.

### Key Entities _(include if feature involves data)_

- **Session**: A single runtime narrative experiment identified by a session identifier, with lifecycle status, elapsed time, and budget/coherence telemetry.
- **Scene Node**: A narrative unit containing scene text, entropy profile, activation metadata, and termination vote state.
- **Narrative Edge**: A relationship between scene nodes describing narrative linkage type and lock/protection status.
- **Mutation Event**: A timestamped record describing attempted or applied topology changes, including actor, target, and outcome.
- **Termination Vote State**: Aggregated active-node voting status that determines whether the session should conclude.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: In moderated tests, 95% of valid seeds produce an initial scene within 2 seconds.
- **SC-002**: During 30-minute autonomous sessions, global coherence remains at or above 0.80 on average.
- **SC-003**: During entropy-threshold breaches (`ENTROPY_BREACH_THRESHOLD` from plan.md), 95% of required mutation responses are applied within 5 seconds.
- **SC-004**: At least one complete narrative arc (seed through termination) completes in under 10 minutes in a standard run (one foreground session using the documented defaults in plan.md).
- **SC-005**: At least 70% of accepted mutations show improvement in downstream entropy within two subsequent activation cycles.
- **SC-006**: Median per-session operating cost remains below $5 for standard 30-minute runs.
- **SC-007**: In mutation-cycle audits, 100% of cycles emit no more than one activation and no more than one mutation terminal outcome.

## Assumptions

- Sessions are single-user, ephemeral, and do not require cross-session persistence for this MVP.
- Users run the feature in a terminal environment that supports interactive command input and explicit continue-cycle controls.
- Users need export artifacts for analysis, but durable user accounts and collaboration are out of scope.
- Command-driven controls for lock, fork, inspect, pause/resume, and export are available within the same terminal workflow.
- The product team will define and maintain coherence and entropy evaluation rubrics consistently across validation runs.
- A standard run means one foreground session started with the documented defaults in plan.md, one valid seed, and explicit user-issued cycle advancement during observation.
