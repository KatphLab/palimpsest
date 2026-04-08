"""File-backed storage for graph lineage and ancestry lookups."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from models.common import StrictBaseModel
from models.graph_lineage import GraphLineage
from utils.uuid_validation import ensure_valid_uuid

__all__ = ["LineageSchema", "LineageStore"]


class LineageSchema(StrictBaseModel):
    """Serialized lineage document schema for lineage.json."""

    lineages: list[GraphLineage] = Field(default_factory=list)


class LineageStore:
    """Track graph ancestry relationships using a JSON lineage index."""

    def __init__(
        self,
        *,
        root_dir: Path,
        storage_dir_name: str = ".graphs",
        lineage_file_name: str = "lineage.json",
    ) -> None:
        self._root_dir = root_dir
        self._storage_dir = self._root_dir / storage_dir_name
        self._lineage_path = self._storage_dir / lineage_file_name
        self._ensure_storage()

    def add_lineage(self, lineage: GraphLineage) -> None:
        """Insert a lineage record, rejecting duplicate parent-child links."""

        schema = self._read_schema()
        if any(
            item.parent_graph_id == lineage.parent_graph_id
            and item.child_graph_id == lineage.child_graph_id
            for item in schema.lineages
        ):
            raise ValueError(
                "lineage relationship already exists "
                f"({lineage.parent_graph_id} -> {lineage.child_graph_id})"
            )

        schema.lineages.append(lineage)
        self._write_schema(schema)

    def get_parent(self, child_graph_id: str) -> str | None:
        """Return a graph's parent identifier or ``None`` if root."""

        normalized_child_id = ensure_valid_uuid(
            child_graph_id, field_name="child_graph_id"
        )
        schema = self._read_schema()
        for lineage in schema.lineages:
            if lineage.child_graph_id == normalized_child_id:
                return lineage.parent_graph_id

        return None

    def get_children(self, parent_graph_id: str) -> list[str]:
        """Return all direct children for the supplied parent graph ID."""

        normalized_parent_id = ensure_valid_uuid(
            parent_graph_id,
            field_name="parent_graph_id",
        )
        schema = self._read_schema()
        return [
            lineage.child_graph_id
            for lineage in schema.lineages
            if lineage.parent_graph_id == normalized_parent_id
        ]

    def get_ancestry(self, graph_id: str) -> list[GraphLineage]:
        """Return lineage links from root to the requested graph."""

        current_id = ensure_valid_uuid(graph_id, field_name="graph_id")
        schema = self._read_schema()
        lineages_by_child = {
            lineage.child_graph_id: lineage for lineage in schema.lineages
        }

        ancestry: list[GraphLineage] = []
        visited: set[str] = set()
        while current_id in lineages_by_child:
            if current_id in visited:
                raise ValueError(f"lineage cycle detected at graph {current_id}")

            visited.add(current_id)
            lineage = lineages_by_child[current_id]
            ancestry.append(lineage)
            current_id = lineage.parent_graph_id

        ancestry.reverse()
        return ancestry

    def _ensure_storage(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        if not self._lineage_path.exists():
            self._write_schema(LineageSchema())

    def _read_schema(self) -> LineageSchema:
        return LineageSchema.model_validate_json(
            self._lineage_path.read_text(encoding="utf-8")
        )

    def _write_schema(self, schema: LineageSchema) -> None:
        self._lineage_path.write_text(
            schema.model_dump_json(indent=2), encoding="utf-8"
        )
