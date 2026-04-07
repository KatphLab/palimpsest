# Terminal Self-Editing Narrative MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a terminal-first MVP where a Textual TUI (with plain CLI fallback) drives a LangGraph-orchestrated, NetworkX-backed narrative runtime that accepts a seed, grows a live graph, and supports pause/resume, lock/unlock, fork, inspect, export, and telemetry controls.

**Spec Version:** 1.2.0

**Architecture:** Keep the runtime single-process and session-scoped with one state owner (`SessionRuntime`) and typed message passing to the UI. Use Pydantic models for every command, graph, event, and export contract; a NetworkX graph service for topology mutation; LangGraph agents for scene generation and mutation-candidate selection; and an LLM-backed mutation-action proposer that consumes narrative context (last two scenes plus graph metrics) to choose `add_node`/`remove_edge`/`rewrite_node`/`no_op`. LLM selection failures emit telemetry, skip mutation application, and enter backoff before the next retry. Mutation remains serialized to one activation and one mutation resolution per cycle and is advanced explicitly through the TUI continue action. `src/main.py` remains the CLI entry point, and existing config helpers stay in `src/config/`.

**Tech Stack:** Python 3.12, uv, Pydantic 2.12, NetworkX 3.6, LangGraph 1.1, langchain-openai 1.1, Textual, pytest.

---

## Summary

Implement a terminal MVP that turns a short story seed into a live narrative graph, advances one cycle at a time through explicit continue actions, enforces graph safety rules, and exposes entropy, LLM-driven mutation-decision logs (console + file), and JSON export.

## Technical Context

**Language/Version:** Python 3.12+
**Primary Dependencies:** NetworkX, LangGraph, langchain-openai, Pydantic, Pydantic Settings, Textual
**Storage:** In-memory session state; JSON export artifacts only
**Testing:** pytest
**Target Platform:** Interactive terminal runtime on a local developer machine
**Project Type:** Terminal / TUI application
**Performance Goals:** Initial scene within 2 seconds; continue-action panel refresh in the same interaction loop; entropy-breach handling within 5 seconds; median session cost below $5
**Constraints:** Session-scoped only; no durable user accounts; no plain-dict contracts; all data classes and payloads must be typed Pydantic models; graph mutations must be bounded and traceable
**Scale/Scope:** Single-user MVP with multiple in-memory sessions allowed (original plus forks), with one foreground session rendered at a time in the terminal

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- [x] Coherence gate: **PASS** — Spec items CA-001 and SC-002 require sustained coherence ≥ 0.80 during long runs; the plan keeps coherence telemetry on every activation and verifies the threshold in a 30-minute simulation test.
- [x] Mutation safety gate: **PASS** — Spec items CA-002, FR-006, and FR-012 require immutable seed protection, locked-edge protection, bounded mutation rates, and traceable event logging; the plan encodes these as graph invariants and mutation rules.
- [x] Contract gate: **PASS** — Spec item CA-003 and the user constraint require typed schemas for sessions, nodes, edges, mutation decisions, and event records; the plan uses Pydantic models only and rejects raw dict contracts.
- [x] Test-first gate: **PASS** — Spec item CA-004 requires failing acceptance tests for seed flow, pause/resume, lock/fork, mutation logging, entropy visibility, termination voting, and budget tracking before implementation.
- [x] Budget gate: **PASS** — Spec items CA-005, FR-015, and SC-006 define budget targets; the plan includes runtime instrumentation and test assertions for the <5s mutation response and <$5 session cost targets.

## Project Structure

### Documentation (this feature)

```text
specs/001-terminal-hypergraph-mvp/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (flat `src/` layout)

```text
src/
├── main.py
├── config/
│   ├── env.py
│   └── logging_config.py
├── agents/
│   ├── __init__.py
│   ├── llm_mutation_proposer.py
│   ├── scene_agent.py
│   ├── mutation_agent.py
│   ├── mutation_engine.py
│   └── narrative_context_builder.py
├── graph/
│   ├── __init__.py
│   └── session_graph.py
├── models/
│   ├── __init__.py
│   ├── session.py
│   ├── node.py
│   ├── edge.py
│   ├── mutation.py
│   ├── narrative_context.py
│   └── events.py
├── runtime/
│   ├── __init__.py
│   └── session_runtime.py
└── tui/
    ├── __init__.py
    ├── app.py
    ├── story_projection.py
    ├── screens.py
    └── widgets.py

tests/
├── test_main.py
├── unit/
│   ├── test_models_base.py
│   ├── test_session_runtime.py
│   ├── test_tui_app.py
│   └── test_tui_story_projection.py
└── integration/
    ├── test_seed_startup_flow.py
    ├── test_pause_resume_flow.py
    ├── test_autonomous_progress_after_start.py
    └── test_live_story_flow_rendering.py
```

**Structure Decision:** Use a flat runtime layout directly under `src/` (for example `src/agents/`, `src/graph/`, `src/models/`, and `src/tui/`), keep the existing `src/config/` helpers, and mirror behavior with `tests/unit/` plus `tests/integration/` for TUI/session orchestration coverage.
Do not introduce a `src/palimpsest/` package; the runtime stays flat under `src/`.

## Contract and Behavior Closure

To remove known ambiguities before implementation, the following constraints are part of this plan and must be reflected in contract docs and tests:

- Command envelope must use a discriminated union keyed by `command_type` so invalid `command_type`/`payload` pairings are rejected at parse time.
- Event records must standardize on `target_ids: list[str]` (not `target_id`) to support multi-target mutation events and consistency with the data model.
- Every mutation proposal must emit at least one `proposed` event and exactly one terminal outcome event (`applied`, `rejected`, or `cooled_down`).
- The autonomous mutation path is producer-separated: mutation proposals come from a dedicated LangGraph mutation-proposer subgraph, not from scene-generation nodes.
- Exactly one activation candidate and at most one mutation proposal are allowed per mutation cycle.
- Accepted `add_node` mutations must trigger immediate scene generation before cycle completion.
- All timestamps in models remain typed `datetime` values in-memory and are serialized as ISO-8601 UTC in JSON boundaries.
- Fork behavior is explicit: forked sessions are independent and may continue running concurrently; UI focus switching must not mutate background sessions.

## Runtime Constants (Spec Clarifications)

These values make previously vague requirements testable and should be exposed as config with documented defaults:

- `STALE_VIEW_GUARDRAIL_MS = 500`
- `GLOBAL_CONSISTENCY_CHECK_INTERVAL_MS = 60000`
- `MUTATION_BURST_TRIGGER_COUNT = 3` within `10 s` triggers an immediate global check.
- `GLOBAL_MUTATION_STORM_THRESHOLD = 5` within `10 s` triggers global cooldown.
- `SESSION_MUTATION_COOLDOWN_MS = 30000`.
- `SESSION_MAX_SEED_LENGTH = 280`
- `ENTROPY_BREACH_THRESHOLD = 0.80`
- `TERMINATION_MAJORITY_THRESHOLD = 0.5` (strictly greater than half of active nodes).
- `SESSION_BUDGET_USD = 5.00`
- `MUTATION_MAX_PROPOSALS_PER_CYCLE = 1`
- `MUTATION_MAX_ACTIVATIONS_PER_CYCLE = 1`

## Mutation Orchestration Clarifications

To keep autonomous mutation behavior deterministic and testable:

- Mutation proposals are produced by a dedicated LangGraph subgraph (`mutation_engine`) that is separate from scene generation.
- The LLM selects exactly one activation candidate node per mutation cycle.
- After candidate selection, an LLM mutation-action stage evaluates narrative interestingness using the latest context (last two scenes + graph counts) and decides the action type.
- The runtime resolves at most one mutation per cycle (applied/rejected/cooled_down).
- Accepted `add_node` mutations trigger immediate scene generation in the same cycle.
- `prune_branch` removes the full targeted subgraph while preserving seed-protected and otherwise protected graph state.
- Mutation-decision telemetry is emitted to both console and rotating file logs for operator visibility.

## Test-First Gate Expansion

Before implementation tasks begin, `tasks.md` must include failing tests mapped to FR/CA IDs, including:

- FR-003 continue-cycle assertions (no background auto-advance; one cycle per continue action).
- FR-007 concurrency assertions for original and forked sessions (independent updates).
- FR-009 event ordering and schema assertions using `target_ids` and monotonic sequences.
- FR-013 deterministic interval and burst-trigger consistency checks.
- FR-015/CA-005 budget telemetry thresholds and alert emission checks.
- Contract-level negative tests for command payload mismatches and forbidden extra fields.

## Post-Design Constitution Re-Check

_GATE: Re-check after Phase 1 design._

- Coherence: **PASS** — `.specify/memory/constitution.md` I, `research.md` §§3-4, `data-model.md` `CoherenceSnapshot.global_score` (target `>= 0.80`), and `quickstart.md` `SESSION_COHERENCE_TARGET=0.80` require explicit coherence tracking with timed checks.
- Mutation safety: **PASS** — `.specify/memory/constitution.md` II, `research.md` §§2 and 6, `data-model.md` validation rules 4-7 and 9, and the typed lock/unlock + mutation event contracts require seed protection, locked-edge protection, bounded mutation, and traceable outcomes.
- Contract: **PASS** — `.specify/memory/constitution.md` III, `research.md` §5, `data-model.md` assumptions, and all contract files require Pydantic v2 shapes with `extra="forbid"`, discriminated command payloads, and no plain-dict subsystem boundaries.
- Test-first: **PASS** — `.specify/memory/constitution.md` IV and the expanded FR/CA-mapped failing-test requirements in this plan require tests before implementation for core session and contract flows.
- Budget: **PASS** — `.specify/memory/constitution.md` V, `research.md` §7, `data-model.md` `BudgetTelemetry`, and `quickstart.md` `SESSION_BUDGET_USD=5.00` keep cost instrumentation and limits explicit.
