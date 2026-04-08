# Implementation Plan: Graph Forking with Multi-Graph View

**Branch**: `002-graph-forking` | **Date**: 2026-04-08 | **Spec**: [specs/002-graph-forking/spec.md](../spec.md)
**Input**: Feature specification from `/specs/002-graph-forking/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Enable users to create narrative graph forks at any edge, creating parallel graph instances that share history up to the fork point but diverge independently. Provide a multi-graph view for browsing, switching between, and managing multiple active graph instances. Support custom seed input for deterministic narrative exploration. All operations maintain strict graph isolation, preserve narrative coherence, and comply with performance budgets (fork <500ms, switch <300ms, multi-graph view <200ms for 50 graphs).

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: NetworkX (graph data structure), LangGraph (agent orchestration), Pydantic (typed schemas), pytest (testing)
**Storage**: File-based persistence (JSON-serialized graph states per Constitution privacy baseline)
**Testing**: pytest with pytest-cov for coverage reporting
**Target Platform**: Linux (local development), cross-platform Python
**Project Type**: Desktop/CLI narrative application with library components
**Performance Goals**:
- Fork creation: <500ms (CA-005)
- Graph switch: <300ms for graphs up to 1000 nodes
- Multi-graph view render: <200ms for up to 50 graphs
**Constraints**:
- Graph isolation must be enforced at in-memory and file-level
- Coherence metric must score >0.7 for all narrative transitions (CA-001)
- Session-scoped runtime (no persistent account systems)
- Single-user local application (no multi-user auth)
**Scale/Scope**:
- Up to 10 parallel graphs for primary workflow (optimized UI)
- Up to 50 graphs supported (functional but potentially degraded UX)
- Graphs with up to 10,000 nodes (functional, performance may degrade)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Coherence gate (CA-001)**: Each fork maintains internal narrative coherence. Coherence metric >0.7 enforced via thematic/logical continuity scoring on all narrative transitions. Spec defines acceptance threshold (SC-001).
- [x] **Mutation safety gate (CA-002)**: Fork operations are atomic and preserve original graph integrity. Fork history up to fork point is immutable post-creation. Mutations scoped to specific graph instances only. Event logging for traceability per FR-009.
- [x] **Contract gate (CA-003)**: Typed contracts defined in spec:
  - `GraphForkRequest`: `{ sourceGraphId: string, forkEdgeId: string, customSeed?: string, label?: string }`
  - `GraphForkResponse`: `{ forkedGraphId: string, forkPoint: EdgeReference, seed: string, creationTime: timestamp }`
  - `MultiGraphView`: `{ graphs: GraphSummary[], activeGraphId: string | null }`
  - `GraphSwitchRequest`: `{ targetGraphId: string }`
- [x] **Test-first gate (CA-004)**: Tests defined before implementation:
  - Test fork creates isolated graph instance
  - Test custom seed produces deterministic output
  - Test multi-graph view returns all active graphs
  - Test graph switch loads correct state
  - Test parallel execution maintains isolation
- [x] **Budget gate (CA-005)**: Latency targets specified with verification:
  - Fork creation: <500ms (measured via structured logging)
  - Multi-graph view: <200ms for up to 50 graphs
  - Graph switch: <300ms
  - All operations logged with timestamps for performance validation (SC-009)

## Project Structure

### Documentation (this feature)

```text
specs/002-graph-forking/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── graph_instance.py      # GraphInstance entity with fork metadata
│   ├── fork_point.py          # ForkPoint entity for fork location tracking
│   ├── graph_lineage.py       # GraphLineage for ancestry tracking
│   ├── seed_config.py         # SeedConfiguration for deterministic generation
│   └── multi_graph_view.py    # MultiGraphViewState for browsing context
├── services/
│   ├── graph_forker.py        # Core forking service with isolation guarantees
│   ├── graph_manager.py       # Multi-graph lifecycle and persistence
│   ├── graph_switcher.py      # Graph switching with state loading
│   └── coherence_scorer.py    # Narrative coherence measurement
├── runtime/
│   ├── multi_graph_executor.py  # Parallel graph execution engine
│   └── graph_registry.py        # Active graph instance registry
├── cli/
│   ├── commands/
│   │   ├── fork.py            # CLI command for forking graphs
│   │   ├── list_graphs.py     # CLI command for multi-graph view
│   │   └── switch_graph.py    # CLI command for graph switching
│   └── ui/
│       └── multi_graph_display.py  # Terminal UI for graph browser
└── persistence/
    ├── graph_store.py         # File-based graph persistence
    └── lineage_store.py       # Fork ancestry persistence

tests/
├── unit/
│   ├── models/
│   │   ├── test_graph_instance.py
│   │   ├── test_fork_point.py
│   │   ├── test_graph_lineage.py
│   │   └── test_seed_config.py
│   └── services/
│       ├── test_graph_forker.py
│       ├── test_graph_manager.py
│       ├── test_graph_switcher.py
│       └── test_coherence_scorer.py
├── integration/
│   ├── test_fork_isolation.py
│   ├── test_parallel_execution.py
│   ├── test_multi_graph_view.py
│   └── test_deterministic_seeds.py
└── contract/
    └── test_typed_contracts.py
```

**Structure Decision**: Single project layout (Option 1) following existing src/ structure with models/, services/, runtime/, cli/, and persistence/ modules. Tests mirror src/ structure with unit/, integration/, and contract/ directories per Constitution test-first requirements.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations. All gates pass.
