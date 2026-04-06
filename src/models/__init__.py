"""Typed model package for runtime contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.mutation import MutationDecision, MutationProposal
from models.node import SceneNode
from models.session import Session, SessionSnapshot

if TYPE_CHECKING:
    from graph.session_graph import GraphEdge

__all__: list[str] = [
    "MutationDecision",
    "MutationProposal",
    "GraphEdge",
    "SceneNode",
    "Session",
    "SessionSnapshot",
]


def __getattr__(name: str) -> type[GraphEdge]:
    """Lazily expose graph edge exports without creating import cycles."""

    if name == "GraphEdge":
        from graph.session_graph import GraphEdge

        return GraphEdge

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
