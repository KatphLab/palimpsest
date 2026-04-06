# Phase 0 Research: Terminal Self-Editing Narrative MVP

This document resolves technical ambiguities for the terminal MVP into implementation-ready decisions.

## 1) Runtime ownership and session control

- Decision: Use a single in-process `SessionRuntime` owner for each session. It owns the mutable NetworkX graph, LangGraph execution, event log, and budget telemetry. The Textual UI only submits commands and renders immutable snapshots; it never mutates session state directly.
- Rationale: A single writer keeps state transitions deterministic, prevents UI/runtime races, and makes pause/resume, fork, and export behavior testable.
- Alternatives considered:
  - Split UI and runtime into separate processes with IPC.
  - Let Textual mutate state directly and treat LangGraph as a library-only helper.

## 2) NetworkX graph modeling

- Decision: Model the narrative as an `nx.MultiDiGraph` with stable `node_id` and `edge_id` values. Use node attributes for scene text, entropy, drift, activation metadata, and termination state. Use edge attributes for relationship type, lock/protection flags, provenance, and mutation lineage. Represent any higher-arity narrative relation as a small edge bundle with a shared `relation_group_id`.
- Rationale: `MultiDiGraph` preserves parallel relationship semantics, supports traceable mutations, and avoids boxing the MVP into a single-edge assumption that would make forks and lineage harder to export.
- Alternatives considered:
  - `nx.DiGraph` with one edge per node pair.
  - A bipartite incidence graph to emulate hyperedges explicitly.

## 3) LangGraph orchestration

- Decision: Use one compiled LangGraph state machine per session with typed Pydantic state. The graph should include explicit nodes for scene generation, entropy and drift evaluation, mutation proposal, safety filtering, consistency checks, and termination voting. All model outputs are validated before they can update the session graph.
- Rationale: A state machine matches the session lifecycle, makes safety gates explicit, and keeps mutation control separate from narrative generation. Typed state also makes retries and test doubles straightforward.
- Alternatives considered:
  - A single linear chain of agent calls.
  - Separate ad hoc agent functions coordinated outside LangGraph.

## 4) Textual refresh and event model

- Decision: Run the TUI on the main asyncio loop and publish runtime updates through Textual messages. Use a periodic refresh tick of 250 ms, but only redraw when the session snapshot version changes. Background session work posts immutable snapshot/event messages back to the UI via `call_from_thread` or `post_message`.
- Rationale: Message passing avoids thread-safety issues, while a short tick interval gives headroom to satisfy the 500 ms freshness requirement even under light load.
- Alternatives considered:
  - Pure reactive redraws with no timer.
  - A separate polling thread that reads runtime state directly.

## 5) Pydantic v2 contracts

- Decision: Define all session, node, edge, mutation, event, export, and budget shapes as Pydantic v2 models with `extra='forbid'` and explicit field validation. Use frozen models for immutable snapshots and discriminated unions for event types. No plain dictionaries cross subsystem boundaries.
- Rationale: Strict schemas enforce the constitution's typed-contract requirement, reduce silent drift, and make exported artifacts and tests reliable.
- Alternatives considered:
  - `dataclasses` for internal state and `TypedDict` for payloads.
  - Permissive models that accept extra fields and coerce loosely.

## 6) Export and event logging

- Decision: Maintain an append-only in-memory event log of validated Pydantic event records. Every mutation attempt, veto, safety breach, budget alert, and termination decision appends a record with a monotonic sequence number and timestamp. Export produces a single structured JSON artifact containing the session snapshot, graph contents, and full event log. Runtime diagnostics still use the standard `logging` module, while the event log remains the canonical audit trail.
- Rationale: Append-only events support replay, inspection, and offline analysis while keeping export format deterministic and easy to test.
- Alternatives considered:
  - Text-only logging as the primary audit trail.
  - Snapshot-only export without preserving the event history.

## 7) Budget instrumentation

- Decision: Track budget telemetry as a first-class Pydantic model with per-session estimated cost, token counts, call counts, and latency measurements. Update telemetry on every model call and mutation cycle, emit warning events at the soft threshold, and emit a hard-breach event when the configured budget is exceeded. Prefer provider-reported usage metadata for cost accounting; when unavailable, fall back to a conservative estimate and mark the value as estimated.
- Rationale: Budget visibility must be measurable at runtime and reproducible in tests, not inferred after the fact.
- Alternatives considered:
  - Compute cost only at the end of a session.
  - Ignore provider usage metadata and rely on fixed heuristics only.

## Resulting implementation posture

These decisions lock the MVP into a single-owner, typed, event-driven runtime with NetworkX as the graph store, LangGraph as the orchestration layer, Textual as the presentation layer, and Pydantic v2 as the contract boundary.
