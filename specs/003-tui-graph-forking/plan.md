# Implementation Plan: TUI Multi-Graph Forking

**Branch**: `003-tui-graph-forking` | **Date**: 2026-04-08 | **Spec**: [specs/003-tui-graph-forking/spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-tui-graph-forking/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Integrate graph forking and multi-graph navigation directly into the Textual TUI, and enforce the TUI as the only supported application entrypoint. Users can fork from the current node with `f`, enter a seed for the new graph, switch active graphs with `Tab` / `Shift+Tab`, and view graph position plus active-graph-only running state in the status bar while all graphs continue execution in the background.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: Textual (TUI), NetworkX (graph model), LangGraph (agent orchestration), Pydantic (typed contracts), pytest (verification)
**Storage**: Session-scoped in-memory runtime state with JSON serialization via existing graph persistence components
**Testing**: pytest + pytest-cov (unit, integration, and contract coverage)
**Target Platform**: Linux/macOS terminal runtime (Textual)
**Project Type**: Single-project `src/` Python application with TUI entrypoint
**Performance Goals**:
- Graph switch feedback under 300 ms for up to 10 concurrently running graphs (CA-005)
- Fork confirmation under 1 second under normal local conditions (CA-005)
- Status bar update in the same interaction cycle as graph switch (FR-011)
**Constraints**:
- TUI must remain the sole supported startup/interaction entrypoint (FR-001/FR-002)
- Source graph history must remain isolated and immutable at fork boundary (CA-002)
- Active graph running state must be displayed without background graph status leakage (FR-010)
- Typed request/response contracts must be explicit and validated (CA-003)
**Scale/Scope**:
- Primary interactive workflow: up to 10 active concurrent graph sessions
- Cycling behavior must remain correct with dynamic graph lifecycle changes (completion/removal)
- This plan covers TUI orchestration and entrypoint cleanup only; no new persistence tier

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Coherence gate: fork flow anchors to the selected current node, preserving lineage continuity; validation will rely on fork-flow acceptance tests and existing coherence-scoring hooks.
- [x] Mutation safety gate: plan enforces source-graph immutability at fork, graph boundary isolation, and runtime event traceability during graph switching and background execution.
- [x] Contract gate: new/updated typed payloads include `ForkFromCurrentNodeRequest`, `GraphSwitchRequest`, and `MultiGraphStatusSnapshot` with deterministic state transition expectations.
- [x] Test-first gate: failing tests are planned first for fork hotkey flow, graph cycling, background execution continuity, active-only running status, and non-TUI entrypoint removal.
- [x] Budget gate: explicit latency targets (switch <300 ms, fork <1 s) include benchmark/integration verification strategy.

## Project Structure

### Documentation (this feature)

```text
specs/003-tui-graph-forking/
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
├── main.py                         # Primary app entrypoint (must remain only supported startup)
├── tui/
│   ├── app.py                      # Textual bindings/actions for fork/switch/status updates
│   ├── screens.py                  # Seed/fork prompt screens and submission handlers
│   ├── widgets.py                  # Footer/status widgets and shortcut legends
│   └── story_projection.py         # Active graph scene projection updates
├── runtime/
│   ├── session_runtime.py          # Session orchestration, active graph context, command routing
│   ├── multi_graph_executor.py     # Background execution lifecycle for all graphs
│   └── graph_registry.py           # Isolated graph registration and retrieval
├── models/
│   ├── requests.py                 # Fork/switch request contracts
│   ├── responses.py                # Runtime response and status snapshot contracts
│   └── multi_graph_view.py         # Graph summaries and active/total view models
└── cli/
    └── main.py                     # Legacy alternate entrypoint targeted for removal/deprecation

tests/
├── unit/
│   ├── test_tui_app.py             # Keybinding and active-graph status behavior
│   ├── test_tui_widgets.py         # Footer/status rendering and shortcut updates
│   └── services/
│       ├── test_phase7_graph_forker.py
│       └── test_phase7_graph_switcher.py
├── integration/
│   ├── test_parallel_execution.py  # Background graph progression while inactive
│   └── test_multi_graph_view.py    # Graph index and active/total display integrity
└── contract/
    └── test_multi_graph_view.py    # Typed contract assertions for status/switch payloads
```

**Structure Decision**: Keep the single-project Python `src/` layout and implement behavior in existing TUI/runtime/models modules. Remove or disable non-TUI startup paths so `src/main.py` remains the sole supported entrypoint, while preserving multi-graph execution in runtime services.

## Post-Design Constitution Check

- [x] Coherence gate: design keeps fork origin tied to current selected node and tests narrative continuity around fork start context.
- [x] Mutation safety gate: design constrains fork actions to new graph instances with no cross-graph mutable references and event-log traceability.
- [x] Contract gate: `contracts/tui-multi-graph-control.md` defines typed request/response payloads and deterministic switching semantics.
- [x] Test-first gate: quickstart and planned tests enumerate fail-first scenarios for fork, switching, status accuracy, and entrypoint enforcement.
- [x] Budget gate: quickstart verification includes timing checks aligned to CA-005 thresholds.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations identified.
