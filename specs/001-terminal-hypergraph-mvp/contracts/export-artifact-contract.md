# Export Artifact Contract

**Spec Version**: 1.1.0

Boundary: session runtime -> JSON export file.

The export artifact is a frozen, schema-versioned JSON document for offline analysis and replay.
`SessionEvent` is the typed event model defined in `event-stream-contract.md`.
Mutation lifecycle records in `events` must preserve one-proposal-per-cycle semantics and terminal outcomes.

## Pydantic shapes

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExportNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    label: str
    text: str
    entropy_score: float
    drift_category: str
    is_seed_protected: bool


class ExportEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    locked: bool
    protected_reason: str | None = None


class ExportGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_count: int
    edge_count: int
    nodes: list[ExportNode]
    edges: list[ExportEdge]


class ExportSessionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    status: str
    seed_text: str
    parent_session_id: UUID | None = None
    graph_version: int
    final_coherence_score: float
    estimated_cost_usd: Decimal


class ExportSessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    final_coherence_score: float
    estimated_cost_usd: Decimal
    total_events: int
    terminated_due_to_votes: bool


class ExportArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    exported_at: datetime
    session: ExportSessionSnapshot
    graph: ExportGraph
    events: list["SessionEvent"]
    summary: ExportSessionSummary
```

## Validation rules

- The artifact must be deterministic for a given session snapshot.
- `schema_version` defaults to `"1.0.0"` for MVP exports and must be incremented explicitly if the artifact shape changes.
- `nodes` and `edges` must be serializable without loss of required IDs.
- The seed node must be present in every export.
- `events` must be chronological and complete for the live session window.
- Accepted `add_node` events must be replayable to a created node with non-empty scene text in the same cycle.
- `prune_branch` outcomes must be replayable as full-subgraph removals while preserving protected state.
- The export path must be writable; invalid paths must fail before partial writes occur.

## Requirement coverage

- FR-011: structured JSON export.
- FR-014: final session summary.
- CA-003: typed contract boundary.
- CA-005: cost and termination reporting.
