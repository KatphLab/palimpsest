# Data Model: TUI Multi-Graph Forking

**Feature**: TUI Multi-Graph Forking
**Branch**: 003-tui-graph-forking
**Date**: 2026-04-08

## Entities

### GraphSession

Represents one independently progressing narrative graph tracked by the runtime and rendered in the TUI.

| Field | Type | Required | Description |
|---|---|---|---|
| graph_id | UUID string | Yes | Stable graph identifier |
| current_node_id | string \| null | No | Current focused node for fork/navigation actions |
| execution_status | enum(`idle`,`running`,`paused`,`completed`,`failed`) | Yes | Runtime execution state |
| is_active | bool | Yes | Whether this graph is currently focused in TUI |
| last_activity_at | datetime | Yes | Last progression/update timestamp |

**Validation rules**:
- `graph_id` must be a valid UUID.
- Exactly one `GraphSession` in `GraphRegistry` may have `is_active=True` at a time.
- `current_node_id` must exist in graph topology when present.

### ForkRequest

Represents user intent to branch from the active graph's current node via TUI fork flow.

| Field | Type | Required | Description |
|---|---|---|---|
| active_graph_id | UUID string | Yes | Source graph used for forking |
| current_node_id | string | Yes | Selected node to fork from |
| seed | string \| null | No | User-provided seed; null means default seed behavior |
| confirm | bool | Yes | Whether user confirmed creation |

**Validation rules**:
- `active_graph_id` must refer to current active graph.
- `current_node_id` must resolve in active graph at request time.
- If `confirm=False`, no graph is created.

**State transitions**:
- `draft` -> `confirmed` -> `applied` when user confirms and fork succeeds.
- `draft` -> `cancelled` when user dismisses/cancels prompt.

### GraphRegistry

Ordered runtime collection of available graphs and active index used for graph cycling.

| Field | Type | Required | Description |
|---|---|---|---|
| graph_ids | list[UUID string] | Yes | Ordered graph IDs for cycle navigation |
| active_index | int | Yes | Zero-based index in `graph_ids` |
| total_graphs | int | Yes | Count of tracked graphs |

**Validation rules**:
- `total_graphs == len(graph_ids)`.
- `active_index` must be within range when `total_graphs > 0`.
- `Tab` computes `(active_index + 1) % total_graphs`.
- `Shift+Tab` computes `(active_index - 1) % total_graphs`.

### StatusSnapshot

Payload rendered in status/footer region for active graph context.

| Field | Type | Required | Description |
|---|---|---|---|
| active_position | int | Yes | 1-based active graph position |
| total_graphs | int | Yes | Number of available graphs |
| active_running_state | enum(`idle`,`running`,`paused`,`completed`,`failed`) | Yes | Running state of active graph only |

**Validation rules**:
- `1 <= active_position <= total_graphs` when graphs exist.
- `active_running_state` must come from active graph session only.
- Background graph states must not overwrite `active_running_state`.

## Relationships

- One `GraphRegistry` has many `GraphSession` records.
- One active `GraphSession` can produce many `ForkRequest` attempts over time.
- One successful `ForkRequest` creates one new `GraphSession` appended to `GraphRegistry` ordering.
- One active `GraphSession` maps to one rendered `StatusSnapshot` per refresh cycle.

## Invariants and Safety Rules

- Source graph isolation: forking creates a distinct graph identity and must not mutate source graph history beyond normal progression.
- Active graph uniqueness: only one active graph at a time for interaction routing and status display.
- Deterministic switching: each switch action updates active graph context and status snapshot in same interaction cycle.
- Traceability: fork/switch actions are emitted through command/runtime event logs.
