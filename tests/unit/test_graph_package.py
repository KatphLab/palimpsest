"""Tests for the graph package exports."""

from graph import GraphEdge, GraphNode, SessionGraph
from graph.session_graph import (
    GraphEdge as SessionGraphEdge,
)
from graph.session_graph import (
    GraphNode as SessionGraphNode,
)
from graph.session_graph import (
    SessionGraph as SessionGraphImpl,
)


def test_graph_package_re_exports_session_graph_primitives() -> None:
    """The graph package should expose the session graph primitives."""

    assert GraphEdge is SessionGraphEdge
    assert GraphNode is SessionGraphNode
    assert SessionGraph is SessionGraphImpl
