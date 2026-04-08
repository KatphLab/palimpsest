# Quickstart: Graph Forking with Multi-Graph View

**Feature**: Graph Forking with Multi-Graph View
**Branch**: 002-graph-forking
**Date**: 2026-04-08

## Prerequisites

- Python 3.12+
- Environment installed with `make install`
- Commands run from repository root: `/home/katph/projects/palimpsest`

> These examples are validated by:
>
> - `uv run pytest tests/integration/test_quickstart_validation.py`

## 1) Seed Local Graph Data (one-time for quickstart)

This creates two persisted graphs under `.graphs/` so CLI commands have data to act on.

```bash
PYTHONPATH=src uv run python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from models.graph_instance import GraphInstance, GraphLifecycleState
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore


def build_graph(graph_id: str, edge_id: str = "edge_1") -> GraphInstance:
    graph = nx.DiGraph()
    graph.add_node("n1")
    graph.add_node("n2")
    graph.add_edge("n1", "n2", edge_id=edge_id, coherence_score=0.9)

    now = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)
    return GraphInstance(
        id=graph_id,
        name=f"Graph {graph_id[:8]}",
        created_at=now,
        seed_config=SeedConfiguration.generate(seed="seed-root"),
        graph_data=graph,
        metadata={},
        last_modified=now,
        state=GraphLifecycleState.ACTIVE,
    )


store = GraphStore(root_dir=Path.cwd())
store.save(build_graph("550e8400-e29b-41d4-a716-446655440000"))
store.save(build_graph("550e8400-e29b-41d4-a716-446655440001"))
print("Seeded quickstart graphs")
PY
```

## 2) Fork a Graph

```bash
PYTHONPATH=src uv run python -m cli.main fork \
  --source 550e8400-e29b-41d4-a716-446655440000 \
  --edge edge_1 \
  --seed quickstart-seed \
  --label "Quickstart Fork"
```

What this does:

- Validates source graph and edge
- Enforces coherence and graph-limit policies
- Creates a forked graph with lineage and deterministic seed metadata

## 3) List Graphs

```bash
PYTHONPATH=src uv run python -m cli.main list-graphs --status active
```

Optional filters/sorting:

```bash
PYTHONPATH=src uv run python -m cli.main list-graphs \
  --search "Quickstart" \
  --sort-by name \
  --sort-order asc
```

## 4) Switch Active Graph

```bash
PYTHONPATH=src uv run python -m cli.main switch-graph \
  --target 550e8400-e29b-41d4-a716-446655440001
```

This operation uses optimistic locking (last-write-wins) and logs conflicts.

## 5) Verified Python API Example

```python
import asyncio
from pathlib import Path

from models.requests import GraphForkRequest
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.graph_forker import GraphForker


async def run() -> None:
    root = Path.cwd()
    forker = GraphForker(
        graph_store=GraphStore(root_dir=root),
        lineage_store=LineageStore(root_dir=root),
    )
    response = await forker.fork_graph(
        GraphForkRequest(
            source_graph_id="550e8400-e29b-41d4-a716-446655440000",
            fork_edge_id="edge_1",
            custom_seed="quickstart-python-seed",
            label="Quickstart Python Fork",
        )
    )
    print(response.forked_graph_id, response.seed)


asyncio.run(run())
```

## 6) Performance Targets and Verification

Budgets from CA-005:

- Fork creation: `<500ms`
- Graph switch: `<300ms` for 1,000-node graph
- Multi-graph view: `<200ms` for 50 graphs

Verified by:

```bash
uv run pytest tests/integration/test_phase7_performance.py
```
