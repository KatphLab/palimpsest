# Quickstart: Graph Forking with Multi-Graph View

**Feature**: Graph Forking with Multi-Graph View
**Branch**: 002-graph-forking
**Date**: 2026-04-08

## Overview

This feature enables narrative designers to:
- Create parallel graph instances by forking at any edge
- View and switch between multiple active graphs
- Provide custom seeds for deterministic narrative exploration
- Execute graphs in parallel with full state isolation

## Prerequisites

- Python 3.12+
- Project installed per `make install`
- Existing narrative graph (seed story)

## Basic Usage

### 1. Create a Fork

Fork an existing graph at a specific edge:

```python
from services.graph_forker import GraphForker
from models.requests import GraphForkRequest

# Initialize forker
forker = GraphForker()

# Create a fork
request = GraphForkRequest(
    sourceGraphId="550e8400-e29b-41d4-a716-446655440000",
    forkEdgeId="decision_node_3",
    customSeed="hero_takes_left_path",  # Optional
    label="Alternative: Hero chooses bravery"
)

response = await forker.fork_graph(request)
print(f"Created fork: {response.forkedGraphId}")
print(f"Seed used: {response.seed}")
```

**Without custom seed** (auto-generated):

```python
request = GraphForkRequest(
    sourceGraphId="550e8400-e29b-41d4-a716-446655440000",
    forkEdgeId="decision_node_3"
)
response = await forker.fork_graph(request)
# response.seed contains auto-generated unique seed
```

### 2. View All Graphs

```python
from services.graph_manager import GraphManager
from models.views import FilterState

manager = GraphManager()

# List all active graphs
view = await manager.get_multi_graph_view()
for summary in view.graphs:
    print(f"{summary.name}: {summary.nodeCount} nodes")
    if summary.forkSource:
        print(f"  └─ Forked from: {summary.forkSource}")

# Filter by fork source
filters = FilterState(forkSource="550e8400-e29b-41d4-a716-446655440000")
view = await manager.get_multi_graph_view(filters=filters)
```

### 3. Switch Between Graphs

```python
from models.requests import GraphSwitchRequest

# Switch to a different graph
switch_request = GraphSwitchRequest(
    targetGraphId="660f9511-f30c-52e5-b827-557766551111",
    preserveCurrent=True  # Save current state before switch
)

response = await manager.switch_graph(switch_request)
print(f"Switched in {response.loadTimeMs}ms")
print(f"Active graph: {response.graphSummary.name}")
```

### 4. Parallel Execution

```python
from runtime.multi_graph_executor import MultiGraphExecutor

executor = MultiGraphExecutor(max_parallel=5)

# Start multiple graphs
graph_ids = [
    "550e8400-e29b-41d4-a716-446655440000",  # Original
    "660f9511-f30c-52e5-b827-557766551111",  # Fork 1
    "770g0622-g41d-63f6-c938-668877662222",  # Fork 2
]

for graph_id in graph_ids:
    state = await executor.execute_graph(graph_id)
    print(f"Started {graph_id}: {state.status}")

# Check all execution states
all_states = await executor.get_all_execution_states()
print(f"Running: {all_states.activeCount}/{all_states.maxParallel}")

# Advance individual graphs independently
new_state, result = await executor.advance_step(graph_ids[0])
# graph_ids[1] and graph_ids[2] remain unaffected
```

## CLI Commands

### Fork a graph

```bash
# Fork with custom seed
uv run python -m cli fork \
  --source 550e8400-e29b-41d4-a716-446655440000 \
  --edge decision_node_3 \
  --seed "my_custom_seed" \
  --label "Hero's dark path"

# Fork with auto-generated seed
uv run python -m cli fork \
  --source 550e8400-e29b-41d4-a716-446655440000 \
  --edge decision_node_3
```

### List graphs

```bash
# All graphs
uv run python -m cli graphs list

# Filter by fork source
uv run python -m cli graphs list --forked-from 550e8400-e29b-41d4-a716-446655440000

# Filter by date
uv run python -m cli graphs list --created-after 2026-04-01
```

### Switch graphs

```bash
uv run python -m cli graphs switch 660f9511-f30c-52e5-b827-557766551111
```

### Delete/archive graphs

```bash
# Archive (soft delete, recoverable)
uv run python -m cli graphs archive 660f9511-f30c-52e5-b827-557766551111

# Delete (permanent, fails if has children)
uv run python -m cli graphs delete 660f9511-f30c-52e5-b827-557766551111

# Force delete (removes children references)
uv run python -m cli graphs delete 660f9511-f30c-52e5-b827-557766551111 --force
```

## Deterministic Reproduction

To reproduce the exact same narrative path:

```python
# First fork
fork1 = await forker.fork_graph(GraphForkRequest(
    sourceGraphId="550e8400-e29b-41d4-a716-446655440000",
    forkEdgeId="decision_node_3",
    customSeed="reproducible_seed_42"
))

# Later, recreate identical fork
fork2 = await forker.fork_graph(GraphForkRequest(
    sourceGraphId="550e8400-e29b-41d4-a716-446655440000",
    forkEdgeId="decision_node_3",
    customSeed="reproducible_seed_42"  # Same seed!
))

# Graph IDs are different, but narrative content is identical
assert fork1.forkedGraphId != fork2.forkedGraphId
assert fork1.seed == fork2.seed
```

## Key Concepts

### Graph Isolation

- Each fork is a **deep copy** with independent state
- Shared history (before fork) is **immutable**
- Mutations to one graph never affect others

### Fork Lineage

```
Original Graph
├── Fork A ("Hero takes left")
│   └── Fork A1 ("Left path, dark choice")
└── Fork B ("Hero takes right")
    └── Fork B1 ("Right path, noble choice")
```

Track ancestry:

```python
# Get lineage for a graph
lineage = await manager.get_graph_lineage(fork_id)
print(f"Depth: {lineage.depth}")
print(f"Parent: {lineage.parentGraphId}")
print(f"Branch: {lineage.branchId}")
```

### Performance Expectations

| Operation | Target | Max Nodes |
|-----------|--------|-----------|
| Fork | <500ms | Any |
| Switch | <300ms | 1,000 |
| List view | <200ms | 50 graphs |

### Coherence Validation

All narrative transitions must score >0.7 on coherence:

```python
from services.coherence_scorer import CoherenceScorer

scorer = CoherenceScorer()
score = await scorer.score_transition(graph, edge_id)
assert score > 0.7, f"Coherence too low: {score}"
```

## Common Patterns

### Pattern: Explore Multiple Variants

```python
# Create multiple forks from the same point with different seeds
base_graph = "550e8400-e29b-41d4-a716-446655440000"
fork_edge = "chapter_2_climax"

variants = []
for variant_name in ["heroic", "cautious", "ruthless"]:
    response = await forker.fork_graph(GraphForkRequest(
        sourceGraphId=base_graph,
        forkEdgeId=fork_edge,
        customSeed=f"chapter2_{variant_name}",
        label=f"Variant: {variant_name.title()}"
    ))
    variants.append(response.forkedGraphId)

# Execute all variants in parallel
for vid in variants:
    await executor.execute_graph(vid)
```

### Pattern: Checkpoint and Branch

```python
# Save progress before major decision
checkpoint_edge = "before_final_boss"

# Create strategic save points
save_easy = await forker.fork_graph(GraphForkRequest(
    sourceGraphId=current_graph,
    forkEdgeId=checkpoint_edge,
    label="Save: Easy mode attempt"
))

save_hard = await forker.fork_graph(GraphForkRequest(
    sourceGraphId=current_graph,
    forkEdgeId=checkpoint_edge,
    label="Save: Hard mode attempt"
))

# Try both approaches independently
```

### Pattern: Batch Operations

```python
# Perform operations on multiple graphs
view = await manager.get_multi_graph_view()

# Archive old graphs
old_graphs = [
    g for g in view.graphs
    if g.createdAt < datetime.now() - timedelta(days=7)
]

for summary in old_graphs:
    await manager.archive_graph(summary.id)
```

## Troubleshooting

### Fork creation slow?

- Check graph size: graphs >10,000 nodes may exceed 500ms target
- Consider archiving old forks to reduce index size

### Can't switch graphs?

```python
# Verify graph exists
view = await manager.get_multi_graph_view()
if target_id not in [g.id for g in view.graphs]:
    print("Graph not found or archived")
```

### Determinism issues?

- Verify same seed, same edge, same source graph state
- Graph ID will always differ (UUID-based)
- Only narrative content is deterministic

## Next Steps

- See [data-model.md](./data-model.md) for entity details
- See [contracts/graph-forking.md](./contracts/graph-forking.md) for API specs
- Run tests: `uv run pytest tests/integration/test_fork_isolation.py`
