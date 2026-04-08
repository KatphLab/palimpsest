# Research: TUI Multi-Graph Forking

**Feature**: TUI Multi-Graph Forking
**Branch**: 003-tui-graph-forking
**Date**: 2026-04-08

## Research Tasks

### Task: TUI-only entrypoint strategy

**Decision**: Keep `src/main.py` as the sole supported startup path and remove/deprecate graph workflow startup through `src/cli/main.py`.

**Rationale**:
- FR-001 and FR-002 require a single supported entrypoint through TUI.
- Existing `src/main.py` already boots `SessionApp` and `SessionRuntime` directly.
- Consolidating startup avoids drift between TUI behavior and out-of-band command handlers.

**Alternatives considered**:
- Keep both TUI and CLI entrypoints with warnings: rejected because it does not satisfy the explicit "only entrypoint" requirement.
- Introduce wrapper binary that dispatches to both: rejected because it preserves multiple entry behaviors.

### Task: Fork-from-current-node interaction model

**Decision**: Add an `f` binding in the Textual app that opens a fork seed prompt sourced from the active graph context, then executes fork confirmation/cancel flow.

**Rationale**:
- Direct keybinding satisfies FR-003 and keeps interaction fully in-TUI.
- Prompt-first flow with explicit confirm/cancel aligns with FR-004 and acceptance scenarios.
- Active-node-scoped forking preserves narrative continuity intent in CA-001.

**Alternatives considered**:
- Modal-less one-key immediate fork using default seed: rejected because seed entry/confirmation is required.
- Reusing external CLI `fork` command from TUI shell-out: rejected because it breaks TUI-only interaction and introduces synchronization risk.

### Task: Graph cycling and active status projection

**Decision**: Model active graph position in an ordered runtime registry and expose a `MultiGraphStatusSnapshot` consumed by footer/status rendering; bind `Tab` for next and `Shift+Tab` for previous.

**Rationale**:
- FR-007, FR-008, and FR-011 require deterministic ordering and immediate feedback.
- A snapshot model creates a single source of truth for active index, total graphs, and active running status.
- Separate projection from rendering allows unit-level contract tests plus integration coverage.

**Alternatives considered**:
- Compute index directly inside widget rendering from arbitrary graph dictionaries: rejected due to ordering instability and duplicate logic.
- Poll full executor state each refresh without snapshot model: rejected due to weaker contract guarantees.

### Task: Background execution when graph is not active

**Decision**: Continue using `MultiGraphExecutor` for graph progression independent of TUI focus, while status area renders only active graph run state.

**Rationale**:
- Existing executor already supports concurrent managed graph states with pause/resume/advance behavior.
- FR-009 and FR-010 require decoupling execution from visual focus.
- Maintaining active-only status projection avoids cognitive overload from background status noise.

**Alternatives considered**:
- Pause all inactive graphs automatically: rejected because it violates FR-009.
- Show aggregate running state for all graphs in primary status line: rejected because FR-010 mandates active-only running status display.

### Task: Budget verification approach

**Decision**: Verify switch/fork latency with integration timing assertions and existing runtime structured logging; keep thresholds aligned to CA-005.

**Rationale**:
- Constitution Principle V requires measurable proof of latency/cost constraints.
- Existing tests already exercise runtime execution paths and can be extended to include timing checks for new TUI orchestration paths.
- Integration + logs provide both regression detection and diagnosability.

**Alternatives considered**:
- Manual-only timing validation: rejected because it is not automation-backed.
- Microbenchmarks only, no integration checks: rejected because user-visible workflow includes TUI orchestration overhead.

## Open Questions

None. Technical context clarifications are resolved.
