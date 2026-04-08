<!--
Sync Impact Report
Version change: 1.0.0 -> 1.1.0
Modified principles:
- No principle changes (names and content unchanged)
- Project name standardized: "SENH" now clarified as "Palimpsest (Self-Editing Narrative Hypergraph)"
Added sections:
- None
Removed sections:
- None
Templates requiring updates:
- ✅ verified `.specify/templates/plan-template.md` (Constitution Check references all 5 principles)
- ✅ verified `.specify/templates/spec-template.md` (Constitution Alignment references all 5 principles)
- ✅ verified `.specify/templates/tasks-template.md` (includes coherence/latency/cost instrumentation tasks)
- ✅ verified `.specify/templates/commands/` (no command templates present - nothing to update)
- ✅ verified `AGENTS.md` (operational guidance aligns with constitution)
- ✅ verified `README.md` (architecture aligns with principles)
Follow-up TODOs:
- None
-->

# Palimpsest Constitution

**Project**: Palimpsest (Self-Editing Narrative Hypergraph)
**Short Name**: SENH

## Core Principles

### I. Narrative Coherence First
All graph mutations, node activations, and pruning operations MUST preserve or improve
global narrative coherence. The system MUST continuously track coherence with explicit
metrics and MUST fail fast when coherence drops below agreed thresholds. Rationale:
Palimpsest exists to produce coherent-yet-unpredictable stories, so coherence is the primary
quality target and takes precedence over mutation volume.

### II. Safe, Bounded Graph Mutation
Graph-editing capabilities MUST be constrained by explicit invariants: seed node
immutability, locked-edge protection, mutation rate limits, and bounded graph size.
Each activation MUST perform at most one mutation unless an approved protocol states
otherwise, and every mutation MUST be traceable in an event log. Rationale: unconstrained
self-modification can collapse story structure and system stability.

### III. Typed Contracts and Deterministic State Evolution
All external and internal mutation payloads MUST use explicit typed schemas, and graph
state transitions MUST be reproducible from logged events under fixed inputs. New public
interfaces MUST define request/response contracts before implementation. Rationale:
typed contracts prevent silent drift, and deterministic replay makes debugging and
research-grade analysis possible.

### IV. Test-First Verification Gates
Work MUST follow test-first development for new behavior and bug fixes: define failing
tests, implement minimal passing changes, then refactor safely. Changes touching agent
orchestration, mutation logic, or schema contracts MUST include integration coverage.
No feature is complete without automated tests that validate the intended behavior.
Rationale: emergent systems are high-risk for regressions without strict verification.

### V. Budgeted Runtime Performance and Cost
Session-level latency and API cost budgets MUST be defined in every feature spec, and
implementations MUST include instrumentation that proves budget adherence in tests or
benchmarks. If a change improves quality but exceeds budget, it MUST include a documented
mitigation plan before merge. Rationale: Palimpsest is a real-time prototype and must remain
operable within practical cost and responsiveness limits.

## Technical and Product Constraints

- Primary implementation language MUST be Python 3.12+ with a `src/` layout.
- Dependency and environment management MUST use `uv`; manual edits to `uv.lock` are
  prohibited.
- Core graph representation MUST use NetworkX-compatible structures and JSON-serializable
  mutation events.
- Runtime is session-scoped: persistent account systems and cross-session memory are out
  of scope unless explicitly added by a future amendment.
- Privacy baseline: user seed content and generated narrative state MUST not be written to
  persistent storage by default.

## Development Workflow and Review Gates

1. Every implementation plan MUST include a Constitution Check that maps planned work to
   all five core principles.
2. Every feature spec MUST define measurable coherence, latency, and cost outcomes.
3. Every task list MUST include explicit test tasks before implementation tasks for each
   user story.
4. Pull requests MUST include evidence for: schema validation, mutation safety rules, and
   budget instrumentation.
5. Reviewers MUST block merges when constitutional requirements are missing or unverifiable.

## Governance
This constitution is the authoritative engineering policy for Palimpsest and supersedes
conflicting local conventions.

- Amendment Process: propose changes via PR that includes rationale, impacted principles,
  and template/document synchronization updates.
- Approval Rule: at least one maintainer approval is required for PATCH amendments; at
  least two maintainer approvals are required for MINOR or MAJOR amendments.
- Versioning Policy: use semantic versioning for governance documents.
  - MAJOR: incompatible principle removal or redefinition.
  - MINOR: new principle/section or materially expanded guidance.
  - PATCH: clarifications, wording improvements, typo fixes, and non-semantic edits.
- Compliance Review: every plan, spec, tasks document, and PR review MUST include an
  explicit constitution compliance check.
- Operational Guidance: `AGENTS.md` defines daily coding practices that implement this
  constitution.

**Version**: 1.1.0 | **Ratified**: 2026-04-06 | **Last Amended**: 2026-04-08
