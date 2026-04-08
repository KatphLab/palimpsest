# Research: Graph Forking with Multi-Graph View

**Feature**: Graph Forking with Multi-Graph View
**Branch**: 002-graph-forking
**Date**: 2026-04-08

## Research Tasks

No unknowns requiring external research. All technical decisions resolved based on:
- Project Constitution constraints
- Existing codebase architecture (NetworkX + LangGraph)
- Feature specification requirements

## Design Decisions

### Decision 1: Graph Isolation Strategy

**Decision**: Deep copy of graph structure with shared immutable history

**Rationale**:
- NetworkX DiGraph supports efficient copying via `copy()` method
- History up to fork point must be immutable per CA-002
- Deep copy ensures complete isolation while preserving lineage tracking

**Alternatives considered**:
- Shallow copy with reference counting: Rejected - violates strict isolation requirement
- Copy-on-write optimization: Rejected - premature optimization, add complexity if needed later

### Decision 2: Seed Handling for Determinism

**Decision**: String-based seeds with hash-derived numeric state for RNG

**Rationale**:
- User-friendly input (strings) with deterministic numeric conversion
- Python's `hash()` or `hashlib` for consistent string-to-int mapping
- Per-graph seed scoping prevents collisions between forks

**Alternatives considered**:
- UUID-based auto-seeds: Rejected - user wants custom seed input capability
- Complex seed objects: Rejected - out of scope per spec assumptions

### Decision 3: Multi-Graph Execution Model

**Decision**: Sequential execution with state isolation, not true parallelism

**Rationale**:
- Python GIL limits true parallelism without multiprocessing
- Sequential execution with proper state management meets "parallel" semantics
- Avoids complexity of multiprocessing for local CLI tool

**Alternatives considered**:
- asyncio concurrent execution: Deferred - evaluate if latency requirements not met
- multiprocessing.Process: Rejected - excessive complexity for current scale

### Decision 4: Persistence Strategy

**Decision**: JSON-serialized graph states with separate lineage metadata file

**Rationale**:
- Aligns with Constitution privacy baseline (file-based, not persistent storage)
- NetworkX supports JSON serialization via node_link_data
- Separate lineage file enables efficient graph listing without loading full graphs

**Alternatives considered**:
- SQLite database: Rejected - violates session-scoped, transient data policy
- Pickle serialization: Rejected - security concerns, not human-readable

### Decision 5: Coherence Measurement

**Decision**: Thematic + logical continuity scoring via edge weight analysis

**Rationale**:
- NetworkX edge attributes can store coherence scores
- Edge weights provide semantic distance metric
- >0.7 threshold aligns with spec CA-001

**Alternatives considered**:
- External ML model: Rejected - budget/complexity, use existing graph metrics
- Node-level scoring: Rejected - narrative coherence is path/edge property

### Decision 6: Conflict Resolution

**Decision**: Optimistic locking with last-write-wins per spec clarification

**Rationale**:
- Single-user application per assumptions
- User notification on conflict per spec clarification Q&A
- Simple timestamp-based versioning

**Alternatives considered**:
- MVCC with branching: Rejected - excessive for single-user app
- Pessimistic locking: Rejected - blocks background operations

## Research Artifacts

None required - all decisions based on existing project knowledge and constraints.

## Open Questions

None - all technical unknowns resolved.
