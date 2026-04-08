"""Registry for active graph instances with isolation enforcement."""

from __future__ import annotations

import copy

from pydantic import ConfigDict

from models.common import StrictBaseModel, UTCDateTime
from models.execution import IsolationViolation
from models.graph_instance import GraphInstance
from utils.time import utc_now

__all__ = ["GraphRegistry", "GraphRegistryEntry"]


class GraphRegistryEntry(StrictBaseModel):
    """Tracked registry entry for one active graph instance."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    graph: GraphInstance
    registered_at: UTCDateTime


class GraphRegistry:
    """Manage active graph instances with deep-copy isolation guarantees."""

    def __init__(self) -> None:
        self._entries: dict[str, GraphRegistryEntry] = {}

    def register(self, graph: GraphInstance) -> GraphInstance:
        """Register a graph instance and return an isolated copy."""

        isolated_graph = copy.deepcopy(graph)
        self._entries[isolated_graph.id] = GraphRegistryEntry(
            graph=isolated_graph,
            registered_at=utc_now(),
        )
        self._enforce_memory_isolation(isolated_graph.id)
        return copy.deepcopy(isolated_graph)

    def update(self, graph: GraphInstance) -> GraphInstance:
        """Replace a tracked graph instance with a freshly isolated copy."""

        return self.register(graph)

    def get(self, graph_id: str) -> GraphInstance:
        """Return a defensive deep copy of a tracked graph instance."""

        try:
            entry = self._entries[graph_id]
        except KeyError as error:
            raise KeyError(f"graph not registered: {graph_id}") from error

        return copy.deepcopy(entry.graph)

    def remove(self, graph_id: str) -> None:
        """Remove a graph from active tracking if present."""

        self._entries.pop(graph_id, None)

    def ids(self) -> tuple[str, ...]:
        """Return sorted identifiers for currently tracked graphs."""

        return tuple(sorted(self._entries.keys()))

    def count(self) -> int:
        """Return count of currently tracked graph instances."""

        return len(self._entries)

    def all_graphs(self) -> list[GraphInstance]:
        """Return defensive copies for all tracked graph instances."""

        return [copy.deepcopy(entry.graph) for entry in self._entries.values()]

    def detect_isolation_violation(self, graph_id: str) -> IsolationViolation | None:
        """Return the first detected memory-isolation violation for a graph."""

        source = self._entries.get(graph_id)
        if source is None:
            return None

        for other_id, other in self._entries.items():
            if other_id == graph_id:
                continue

            if source.graph.graph_data is other.graph.graph_data:
                return IsolationViolation(
                    violation_type="memory",
                    source_graph_id=graph_id,
                    affected_graph_id=other_id,
                    description="graph_data object is shared between graph instances",
                    detected_at=utc_now(),
                )

            if source.graph.metadata is other.graph.metadata:
                return IsolationViolation(
                    violation_type="state",
                    source_graph_id=graph_id,
                    affected_graph_id=other_id,
                    description="metadata dictionary is shared between graph instances",
                    detected_at=utc_now(),
                )

        return None

    def _enforce_memory_isolation(self, graph_id: str) -> None:
        """Raise when a tracked graph violates deep-copy isolation guarantees."""

        violation = self.detect_isolation_violation(graph_id)
        if violation is None:
            return

        raise ValueError(violation.description)
