# Data Model: Graph Forking with Multi-Graph View

**Feature**: Graph Forking with Multi-Graph View
**Branch**: 002-graph-forking
**Date**: 2026-04-08

## Entity Relationship Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GraphInstance  │────<│   ForkPoint     │>────│  GraphLineage   │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ id: string      │     │ sourceGraphId   │     │ parentGraphId   │
│ name: string    │     │ forkEdgeId      │     │ childGraphId    │
│ createdAt: ts │     │ timestamp       │     │ depth: int      │
│ forkPoint: ref│>────│ label?: string  │     │ branchId: string│
│ seedConfig:ref│>────└─────────────────┘     └─────────────────┘
│ graphData: nx │
│ metadata: dict│
└─────────────────┘
         │
         │ 1:1
         ▼
┌─────────────────┐
│ SeedConfiguration│
├─────────────────┤
│ seed: string    │
│ algorithm: str  │
│ deterministic:bool
└─────────────────┘

┌─────────────────────┐
│  MultiGraphViewState │
├─────────────────────┤
│ graphs: GraphSummary[]
│ activeGraphId: string│
│ filters: FilterState │
│ viewPrefs: dict      │
└─────────────────────┘

┌─────────────────┐
│  GraphSummary   │
├─────────────────┤
│ id: string      │
│ name: string    │
│ nodeCount: int  │
│ edgeCount: int  │
│ createdAt: ts   │
│ forkSource: ref │
│ currentState: str │
└─────────────────┘
```

## Entities

### GraphInstance

Represents a single narrative graph with complete isolation from other instances.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier (UUID) |
| name | string | Yes | Human-readable graph name |
| createdAt | datetime | Yes | Creation timestamp |
| forkPoint | ForkPoint\|null | No | Reference to fork origin, null for root graphs |
| seedConfig | SeedConfiguration | Yes | Seed settings for this graph |
| graphData | NetworkX DiGraph | Yes | The actual graph structure (nodes, edges, attributes) |
| metadata | dict | Yes | Additional metadata (coherence scores, labels, etc.) |
| lastModified | datetime | Yes | Timestamp for optimistic locking |

**Validation Rules**:
- `id` must be valid UUID format
- `name` must be 1-100 characters
- `graphData` must be valid NetworkX DiGraph
- If `forkPoint` is null, this is a root graph (no parent)
- `lastModified` must be updated on every mutation

**State Transitions**:
- `created` → `active` → `archived`|`deleted`
- Fork operation: `active` → `forking` → `active` (creates new `active` child)

### ForkPoint

Represents the location and metadata where a fork was created.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| sourceGraphId | string | Yes | ID of the parent graph |
| forkEdgeId | string | Yes | ID of the specific edge where fork occurred |
| timestamp | datetime | Yes | When the fork was created |
| label | string\|null | No | Optional user-provided label for the fork |

**Validation Rules**:
- `sourceGraphId` must reference an existing GraphInstance
- `forkEdgeId` must exist in the source graph at fork time
- `timestamp` is immutable after creation

### GraphLineage

Tracks hierarchical relationships between graphs in a fork tree.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| parentGraphId | string | Yes | Parent graph identifier |
| childGraphId | string | Yes | Child (forked) graph identifier |
| depth | int | Yes | Depth in fork tree (0 = root, 1 = first fork, etc.) |
| branchId | string | Yes | Branch identifier for this lineage path |

**Validation Rules**:
- `depth` must be non-negative integer
- `parentGraphId` != `childGraphId` (no self-references)
- Composite key: (`parentGraphId`, `childGraphId`) must be unique

**Lineage Rules**:
- Root graphs have no lineage entry as child
- Each fork creates one lineage entry
- Tree structure: each graph has 0..N children, 0..1 parent
- Deleting parent does not delete lineage (forks become independent)

### SeedConfiguration

Stores seed settings for deterministic narrative generation.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| seed | string | Yes | The seed value (custom or auto-generated) |
| algorithm | string | Yes | RNG algorithm identifier (default: "python_hash") |
| deterministic | bool | Yes | Whether to use deterministic mode (always true for forks) |

**Validation Rules**:
- `seed` must be 1-255 characters
- `algorithm` must be from supported list: ["python_hash", "sha256"]
- `deterministic` is always true for forked graphs

**Auto-Generation**:
- If user provides no seed, generate random string (16 chars, alphanumeric)
- Store original string for reproducibility

### MultiGraphViewState

Represents the user's current browsing context in the multi-graph view.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| graphs | GraphSummary[] | Yes | List of visible graph summaries |
| activeGraphId | string\|null | No | Currently selected graph ID |
| filters | FilterState | Yes | Active filters and search state |
| viewPrefs | dict | Yes | UI preferences (sort order, display mode) |

**FilterState**:
| Field | Type | Description |
|-------|------|-------------|
| searchQuery | string\|null | Text search across names and labels |
| forkSource | string\|null | Filter by parent graph ID |
| createdAfter | datetime\|null | Filter graphs created after date |
| createdBefore | datetime\|null | Filter graphs created before date |
| status | string\|null | Filter by status (active, archived) |

### GraphSummary

Lightweight representation for list views (performance optimization).

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Graph identifier |
| name | string | Yes | Graph name |
| nodeCount | int | Yes | Number of nodes in graph |
| edgeCount | int | Yes | Number of edges in graph |
| createdAt | datetime | Yes | Creation timestamp |
| forkSource | string\|null | No | Parent graph ID if forked |
| currentState | string | Yes | Current state description |
| lastModified | datetime | Yes | For conflict detection |

## Relationships

| Relationship | Type | Description |
|-------------|------|-------------|
| GraphInstance → ForkPoint | 0..1 | Each graph may have a fork origin |
| GraphInstance → SeedConfiguration | 1..1 | Every graph has seed config |
| GraphInstance → GraphLineage | 0..1 as child | Each graph has 0..1 parent lineage |
| GraphLineage → GraphInstance (parent) | 1..1 | Each lineage references parent |
| GraphLineage → GraphInstance (child) | 1..1 | Each lineage references child |
| MultiGraphViewState → GraphSummary | 0..N | View shows summaries of all graphs |
| GraphInstance → GraphSummary | 1..1 | Summary derived from full instance |

## Coherence Tracking

Coherence is tracked at the edge level within `graphData`:

```python
# Stored as edge attributes in NetworkX
edge_attrs = {
    "coherence_score": 0.85,  # 0.0 to 1.0, must be >0.7
    "thematic_continuity": 0.9,  # Thematic alignment component
    "logical_continuity": 0.8,   # Logical flow component
    "last_evaluated": timestamp
}
```

**Validation Rule**: All edges must have `coherence_score > 0.7` per CA-001.

## Persistence Mapping

**File Structure**:
```
.graphs/
├── index.json           # GraphSummary[] for all graphs
├── lineage.json         # GraphLineage[] for all fork relationships
└── {graph_id}.json      # Individual GraphInstance (serialized graphData)
```

**Serialization**:
- `graphData`: NetworkX node_link_data format
- All datetime fields: ISO 8601 strings
- All entities: Pydantic models with validation

## State Transitions

### Graph Lifecycle

```
┌─────────┐   create    ┌─────────┐   fork      ┌─────────┐
│  none   │────────────>│ created │────────────>│ active  │
└─────────┘             └─────────┘             └────┬────┘
                                                     │
                          ┌──────────────────────────┼──────────┐
                          │                          │          │
                          ▼                          ▼          ▼
                     ┌─────────┐               ┌─────────┐  ┌─────────┐
                     │archived │               │ deleted │  │ parent  │
                     └─────────┘               └─────────┘  │ of new  │
                                                               │  fork   │
                                                               └─────────┘
```

### Fork Operation Flow

1. **Validate**: Source graph exists, edge exists, user has access
2. **Snapshot**: Create deep copy of graph data up to fork edge
3. **Configure**: Set seed (custom or auto-generated)
4. **Create**: New GraphInstance with forkPoint reference
5. **Lineage**: Create GraphLineage entry linking parent→child
6. **Persist**: Save new graph and update lineage index
7. **Return**: GraphForkResponse with new graph details

## Constraints Summary

| Constraint | Enforcement |
|------------|-------------|
| Graph isolation | Deep copy on fork, separate files per graph |
| Immutability | ForkPoint timestamp locked, history frozen |
| Coherence | Edge-level scoring >0.7, validated on mutation |
| Uniqueness | Graph IDs are UUIDs, lineage entries unique |
| Performance | Summary index for multi-graph view, lazy loading |
| Privacy | File-based only, no cloud/external storage |
