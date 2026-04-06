"""Session graph service skeleton for typed topology mutations."""

from __future__ import annotations

from uuid import UUID

import networkx as nx
from pydantic import Field

from models.common import NodeKind, ProtectionReason, RelationType, StrictBaseModel

__all__ = ["GraphEdge", "GraphNode", "SessionGraph"]


class GraphNode(StrictBaseModel):
    """Typed node record stored in the session graph."""

    node_id: str = Field(min_length=1)
    session_id: UUID
    node_kind: NodeKind
    text: str = Field(min_length=1)


class GraphEdge(StrictBaseModel):
    """Typed edge record stored in the session graph."""

    edge_id: str = Field(min_length=1)
    session_id: UUID
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    relation_type: RelationType
    locked: bool = False
    protected_reason: ProtectionReason | None = None


class SessionGraph:
    """NetworkX-backed session graph wrapper with typed primitives."""

    def __init__(self) -> None:
        self._graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()

    @property
    def graph(self) -> nx.MultiDiGraph[str]:
        """Return the owned mutable graph structure."""

        return self._graph

    def add_node(self, node: GraphNode) -> None:
        """Add a typed node to the graph."""

        if self._graph.has_node(node.node_id):
            raise ValueError(f"node '{node.node_id}' already exists")

        self._graph.add_node(node.node_id, node=node)

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a typed edge to the graph."""

        if not self._graph.has_node(edge.source_node_id):
            raise ValueError(f"source node '{edge.source_node_id}' is missing")

        if not self._graph.has_node(edge.target_node_id):
            raise ValueError(f"target node '{edge.target_node_id}' is missing")

        if self.get_edge(edge.edge_id) is not None:
            raise ValueError(f"edge '{edge.edge_id}' already exists")

        self._graph.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            key=edge.edge_id,
            edge=edge,
        )

    def get_edge(self, edge_id: str) -> GraphEdge | None:
        """Return an edge by ID when present."""

        for _, _, _, data in self._graph.edges(keys=True, data=True):
            edge = data.get("edge") if isinstance(data, dict) else None
            if isinstance(edge, GraphEdge) and edge.edge_id == edge_id:
                return edge

        return None

    def remove_edge(self, edge_id: str) -> None:
        """Remove an edge unless it is locked."""

        edge_location = self._find_edge_location(edge_id)
        if edge_location is None:
            raise ValueError(f"edge '{edge_id}' does not exist")

        source_node_id, target_node_id, edge_key, edge = edge_location
        if edge.locked:
            raise ValueError(f"edge '{edge_id}' is locked")

        self._graph.remove_edge(source_node_id, target_node_id, key=edge_key)

    def lock_edge(self, edge_id: str) -> None:
        """Mark an edge as locked and user-protected."""

        self._update_edge(
            edge_id,
            locked=True,
            protected_reason=ProtectionReason.USER_LOCK,
        )

    def unlock_edge(self, edge_id: str) -> None:
        """Clear a lock from a previously locked edge."""

        self._update_edge(edge_id, locked=False, protected_reason=None)

    def _find_edge_location(
        self, edge_id: str
    ) -> tuple[str, str, str, GraphEdge] | None:
        for source_node_id, target_node_id, edge_key, data in self._graph.edges(
            keys=True, data=True
        ):
            edge = data.get("edge") if isinstance(data, dict) else None
            if isinstance(edge, GraphEdge) and edge.edge_id == edge_id:
                return source_node_id, target_node_id, edge_key, edge

        return None

    def _update_edge(
        self,
        edge_id: str,
        *,
        locked: bool,
        protected_reason: ProtectionReason | None,
    ) -> None:
        edge_location = self._find_edge_location(edge_id)
        if edge_location is None:
            raise ValueError(f"edge '{edge_id}' does not exist")

        source_node_id, target_node_id, edge_key, edge = edge_location
        updated_edge = edge.model_copy(
            update={"locked": locked, "protected_reason": protected_reason}
        )
        self._graph[source_node_id][target_node_id][edge_key]["edge"] = updated_edge
