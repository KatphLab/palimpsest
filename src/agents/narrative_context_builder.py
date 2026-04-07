"""Narrative context extraction from the live session graph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict, cast

from graph.session_graph import SessionGraph
from models.common import NodeKind, RelationType
from models.graph import GraphEdge, GraphNode
from models.narrative_context import (
    NarrativeContext,
    NarrativeGraphCounters,
    NarrativeSceneContext,
)
from models.session import Session

__all__ = ["NarrativeContextBuilder"]


class _GraphNodeRecord(TypedDict):
    """Typed view of the graph node payload used by the builder."""

    node: GraphNode


class _GraphEdgeRecord(TypedDict):
    """Typed view of the graph edge payload used by the builder."""

    edge: GraphEdge


class NarrativeContextBuilder:
    """Build mutation-selection context from live session state."""

    def build(
        self,
        session: Session,
        session_graph: SessionGraph,
        activation_candidate_id: str | None,
    ) -> NarrativeContext:
        """Extract the current narrative context from live session state."""

        candidate_node_id = self._normalize_activation_candidate_id(
            activation_candidate_id
        )
        if not session_graph.graph.has_node(candidate_node_id):
            raise ValueError(
                f"activation candidate '{candidate_node_id}' is missing from the graph"
            )

        scene_node_ids = self._scene_node_ids_from_candidate(
            session_graph,
            candidate_node_id,
        )
        if not scene_node_ids:
            raise ValueError("activation candidate does not resolve to a scene")

        if len(scene_node_ids) == 1:
            scene_node_ids = [scene_node_ids[0], scene_node_ids[0]]
        else:
            scene_node_ids = scene_node_ids[-2:]

        scene_contexts = [
            NarrativeSceneContext(
                scene_node_id=node_id,
                scene_text=self._graph_node_text(session_graph, node_id),
            )
            for node_id in scene_node_ids
        ]

        previous_scene, current_scene = scene_contexts
        seed_node_id = self._seed_node_id(session_graph)

        return NarrativeContext(
            session_id=session.session_id,
            seed_node_id=seed_node_id,
            previous_scene_node_id=previous_scene.scene_node_id,
            current_scene_node_id=current_scene.scene_node_id,
            last_two_scenes=scene_contexts,
            graph_counters=NarrativeGraphCounters(
                graph_version=session.graph_version,
                node_count=session_graph.graph.number_of_nodes(),
                edge_count=session_graph.graph.number_of_edges(),
                active_node_count=len(session.active_node_ids),
            ),
        )

    def _normalize_activation_candidate_id(
        self, activation_candidate_id: str | None
    ) -> str:
        if activation_candidate_id is None:
            raise ValueError("activation candidate id is required")

        candidate_node_id = activation_candidate_id.strip()
        if not candidate_node_id:
            raise ValueError("activation candidate id is required")

        return candidate_node_id

    def _scene_node_ids_from_candidate(
        self,
        session_graph: SessionGraph,
        candidate_node_id: str,
    ) -> list[str]:
        scene_node_ids: list[str] = []
        current_node_id = candidate_node_id
        visited_node_ids: set[str] = set()

        while current_node_id not in visited_node_ids:
            visited_node_ids.add(current_node_id)
            graph_node = self._graph_node(session_graph, current_node_id)
            if graph_node.node_kind is NodeKind.SCENE:
                scene_node_ids.append(graph_node.node_id)

            predecessor_edge = self._previous_narrative_edge(
                session_graph,
                current_node_id,
            )
            if predecessor_edge is None:
                break

            current_node_id = predecessor_edge.source_node_id

        scene_node_ids.reverse()
        return scene_node_ids

    def _previous_narrative_edge(
        self,
        session_graph: SessionGraph,
        node_id: str,
    ) -> GraphEdge | None:
        candidate_edges: list[GraphEdge] = []
        for _, _, _, edge_data in session_graph.graph.in_edges(
            node_id, keys=True, data=True
        ):
            edge = self._graph_edge(edge_data)
            if edge is None:
                continue

            if edge.target_node_id != node_id:
                continue

            if edge.relation_type not in {
                RelationType.FOLLOWS,
                RelationType.BRANCHES_FROM,
            }:
                continue

            candidate_edges.append(edge)

        if not candidate_edges:
            return None

        return sorted(
            candidate_edges,
            key=lambda edge: (
                0 if edge.relation_type is RelationType.FOLLOWS else 1,
                edge.created_at,
                edge.edge_id,
            ),
        )[0]

    def _seed_node_id(self, session_graph: SessionGraph) -> str:
        seed_node_ids = [
            node_id
            for node_id, node_data in session_graph.graph.nodes(data=True)
            if self._node_kind(node_data) is NodeKind.SEED
        ]
        if not seed_node_ids:
            raise ValueError("session graph does not contain a seed node")

        return sorted(seed_node_ids)[0]

    def _graph_node(self, session_graph: SessionGraph, node_id: str) -> GraphNode:
        node_data = session_graph.graph.nodes[node_id]
        node_record = cast(_GraphNodeRecord, node_data)
        graph_node = node_record.get("node")
        if not isinstance(graph_node, GraphNode):
            raise ValueError(f"node '{node_id}' is missing graph metadata")

        return graph_node

    def _graph_node_text(self, session_graph: SessionGraph, node_id: str) -> str:
        return self._graph_node(session_graph, node_id).text

    def _graph_edge(self, edge_data: Mapping[str, object]) -> GraphEdge | None:
        edge_record = cast(_GraphEdgeRecord, edge_data)
        edge = edge_record.get("edge")
        return edge if isinstance(edge, GraphEdge) else None

    def _node_kind(self, node_data: Mapping[str, object]) -> NodeKind | None:
        node_record = cast(_GraphNodeRecord, node_data)
        graph_node = node_record.get("node")
        if not isinstance(graph_node, GraphNode):
            return None

        return graph_node.node_kind
