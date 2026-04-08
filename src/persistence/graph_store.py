"""File-based storage for graph instances and graph index summaries."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph
from pydantic import Field, JsonValue

from models.common import StrictBaseModel, UTCDateTime
from models.fork_point import ForkPoint
from models.graph_instance import GraphInstance, GraphLifecycleState
from models.multi_graph_view import GraphSummary
from models.seed_config import SeedConfiguration
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["GraphIndexSchema", "GraphInstanceSchema", "GraphStore"]


class GraphInstanceSchema(StrictBaseModel):
    """Serialized graph instance schema stored on disk."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=100)
    created_at: UTCDateTime
    fork_point: ForkPoint | None = None
    seed_config: SeedConfiguration
    graph_data: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    last_modified: UTCDateTime
    state: GraphLifecycleState = GraphLifecycleState.CREATED


class GraphIndexSchema(StrictBaseModel):
    """Index schema for lightweight graph summaries."""

    graphs: list[GraphSummary] = Field(default_factory=list)


class GraphStore:
    """Persist and retrieve graph instances from local JSON files."""

    def __init__(self, *, root_dir: Path, storage_dir_name: str = ".graphs") -> None:
        self._root_dir = root_dir
        self._storage_dir = self._root_dir / storage_dir_name
        self._index_path = self._storage_dir / "index.json"
        self._ensure_storage()

    def save(self, graph_instance: GraphInstance) -> None:
        """Save a graph instance and refresh its summary in index.json."""

        graph_record = GraphInstanceSchema(
            id=graph_instance.id,
            name=graph_instance.name,
            created_at=graph_instance.created_at,
            fork_point=graph_instance.fork_point,
            seed_config=graph_instance.seed_config,
            graph_data=json_graph.node_link_data(
                graph_instance.graph_data, edges="links"
            ),
            metadata=graph_instance.metadata,
            last_modified=graph_instance.last_modified,
            state=graph_instance.state,
        )

        graph_path = self._graph_path(graph_instance.id)
        graph_path.write_text(graph_record.model_dump_json(indent=2), encoding="utf-8")

        index = self._read_index()
        index.graphs = [
            summary for summary in index.graphs if summary.id != graph_instance.id
        ]
        index.graphs.append(graph_instance.to_summary())
        self._write_index(index)

    def load(self, graph_id: str) -> GraphInstance:
        """Load and deserialize a graph instance by identifier."""

        normalized_graph_id = ensure_valid_uuid(graph_id, field_name="graph_id")
        graph_path = self._graph_path(normalized_graph_id)
        if not graph_path.exists():
            raise FileNotFoundError(f"graph not found: {normalized_graph_id}")

        graph_record = GraphInstanceSchema.model_validate_json(
            graph_path.read_text(encoding="utf-8")
        )
        graph_data = json_graph.node_link_graph(
            graph_record.graph_data,
            directed=True,
            multigraph=False,
            edges="links",
        )

        if not isinstance(graph_data, nx.DiGraph):
            graph_data = nx.DiGraph(graph_data)

        return GraphInstance(
            id=graph_record.id,
            name=graph_record.name,
            created_at=graph_record.created_at,
            fork_point=graph_record.fork_point,
            seed_config=graph_record.seed_config,
            graph_data=graph_data,
            metadata=graph_record.metadata,
            last_modified=graph_record.last_modified,
            state=graph_record.state,
        )

    def delete(self, graph_id: str) -> bool:
        """Delete a graph instance and remove its summary from index.json."""

        normalized_graph_id = ensure_valid_uuid(graph_id, field_name="graph_id")
        graph_path = self._graph_path(normalized_graph_id)
        existed = graph_path.exists()
        if existed:
            graph_path.unlink()

        index = self._read_index()
        index.graphs = [
            summary for summary in index.graphs if summary.id != normalized_graph_id
        ]
        self._write_index(index)
        return existed

    def list_graphs(self) -> list[GraphSummary]:
        """Return all graph summaries from index.json."""

        return self._read_index().graphs

    def _ensure_storage(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            self._write_index(GraphIndexSchema())

    def _read_index(self) -> GraphIndexSchema:
        return GraphIndexSchema.model_validate_json(
            self._index_path.read_text(encoding="utf-8")
        )

    def _write_index(self, index: GraphIndexSchema) -> None:
        self._index_path.write_text(index.model_dump_json(indent=2), encoding="utf-8")

    def _graph_path(self, graph_id: str) -> Path:
        return self._storage_dir / f"{graph_id}.json"
