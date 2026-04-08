# TUI Multi-Graph Control Contract

**Interface**: TUI Runtime Control
**Type**: Internal command and view contract
**Status**: Draft

## ForkFromCurrentNodeRequest

Typed payload emitted by the TUI when user confirms fork (`f`) from current node.

```python
from pydantic import Field

from models.common import StrictBaseModel


class ForkFromCurrentNodeRequest(StrictBaseModel):
    active_graph_id: str = Field(..., description="UUID of active source graph")
    current_node_id: str = Field(..., min_length=1, description="Node to fork from")
    seed: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Optional user seed; null applies default seed behavior",
    )
```

**Validation rules**:
- `active_graph_id` must be a valid UUID and must match active graph context.
- `current_node_id` must exist in active graph.
- `seed` is optional; blank/None falls back to existing default seed behavior.

## GraphSwitchRequest

Typed payload emitted for `Tab`/`Shift+Tab` graph navigation.

```python
from enum import StrEnum
from pydantic import Field

from models.common import StrictBaseModel


class GraphNavigationDirection(StrEnum):
    NEXT = "next"
    PREVIOUS = "previous"


class GraphSwitchRequest(StrictBaseModel):
    target_graph_id: str = Field(..., description="UUID of graph to activate")
    direction: GraphNavigationDirection = Field(
        ...,
        description="Direction used to derive target graph",
    )
```

**Validation rules**:
- `target_graph_id` must exist in runtime graph registry.
- `direction` must be `next` or `previous`.
- Switching must update active context and status snapshot in the same interaction cycle.

## MultiGraphStatusSnapshot

Typed payload used by TUI status/footer render path.

```python
from enum import StrEnum
from pydantic import Field

from models.common import StrictBaseModel


class RunningState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class MultiGraphStatusSnapshot(StrictBaseModel):
    active_position: int = Field(..., ge=1)
    total_graphs: int = Field(..., ge=1)
    active_running_state: RunningState
```

**Validation rules**:
- `active_position <= total_graphs`.
- `active_running_state` must reflect active graph only.
- Background graph statuses must not override this payload.

## Deterministic Transition Expectations

- Fork confirm:
  - Input: `ForkFromCurrentNodeRequest`
  - Output: new graph appended to registry, new graph becomes active.
- Fork cancel:
  - Input: dismissed/negative confirmation
  - Output: no graph created, active graph unchanged.
- Switch next/previous:
  - Input: `GraphSwitchRequest`
  - Output: active graph index updates deterministically by cyclic ordering.
- Status render:
  - Input: runtime active graph context
  - Output: `MultiGraphStatusSnapshot` with active-only running state.
