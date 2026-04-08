"""Graph extraction utilities for typed node and edge access."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from models.common import NodeKind
from models.graph import GraphEdge, GraphNode
from models.node import SceneNode

if TYPE_CHECKING:
    from graph.session_graph import SessionGraph

__all__ = [
    "get_graph_node",
    "get_scene_node",
    "get_node_text",
    "get_node_kind",
    "is_protected_node",
    "get_graph_edge",
    "require_graph_node",
]


def get_graph_node(session_graph: SessionGraph, node_id: str) -> GraphNode | None:
    """Return the GraphNode for a node ID when present and valid."""
    if not session_graph.graph.has_node(node_id):
        return None

    node_data = session_graph.graph.nodes[node_id]
    if not isinstance(node_data, dict):
        return None

    node = node_data.get("node")
    return node if isinstance(node, GraphNode) else None


def get_scene_node(session_graph: SessionGraph, node_id: str) -> SceneNode | None:
    """Return the SceneNode for a node ID when present and valid."""
    if not session_graph.graph.has_node(node_id):
        return None

    node_data = session_graph.graph.nodes[node_id]
    if not isinstance(node_data, dict):
        return None

    scene_node = node_data.get("scene_node")
    return scene_node if isinstance(scene_node, SceneNode) else None


def get_node_text(session_graph: SessionGraph, node_id: str) -> str | None:
    """Return the text content for a node ID when present."""
    graph_node = get_graph_node(session_graph, node_id)
    return graph_node.text if graph_node is not None else None


def get_node_kind(session_graph: SessionGraph, node_id: str) -> NodeKind | None:
    """Return the NodeKind for a node ID when present."""
    graph_node = get_graph_node(session_graph, node_id)
    return graph_node.node_kind if graph_node is not None else None


def is_protected_node(node: GraphNode | SceneNode | None) -> bool:
    """Return whether a node is protected from mutation.

    A node is protected if:
    - It is None (returns False)
    - It is a SceneNode with is_seed_protected=True
    - Its node_kind is NodeKind.SEED
    """
    if node is None:
        return False

    if isinstance(node, SceneNode):
        return node.is_seed_protected or node.node_kind is NodeKind.SEED

    return node.node_kind is NodeKind.SEED


def get_graph_edge(edge_data: Mapping[str, object]) -> GraphEdge | None:
    """Return a GraphEdge from edge data when present and valid."""
    edge = edge_data.get("edge")
    return edge if isinstance(edge, GraphEdge) else None


def require_graph_node(session_graph: SessionGraph, node_id: str) -> GraphNode:
    """Return a GraphNode or raise ValueError if missing.

    Raises:
        ValueError: If the node does not exist or lacks graph metadata.
    """
    graph_node = get_graph_node(session_graph, node_id)
    if graph_node is None:
        raise ValueError(f"node '{node_id}' does not exist")
    return graph_node
