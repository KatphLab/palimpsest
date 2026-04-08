"""Graph forking service with lineage tracking and isolation guarantees."""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from uuid import uuid4

import networkx as nx

from models.errors import ForkErrorCode, GraphForkError
from models.fork_point import ForkPoint
from models.graph_instance import GraphInstance, GraphLifecycleState
from models.graph_lineage import GraphLineage
from models.requests import (
    CUSTOM_SEED_MAX_LENGTH,
    CUSTOM_SEED_MIN_LENGTH,
    GraphForkRequest,
)
from models.responses import EdgeReference, GraphForkResponse
from models.seed_config import SeedConfiguration
from persistence.graph_store import GraphStore
from persistence.lineage_store import LineageStore
from services.structured_logging import OperationLogEntry, log_operation
from utils.time import utc_now

__all__ = ["GraphForker"]


class GraphForker:
    """Create isolated forks from existing graph instances."""

    def __init__(
        self,
        *,
        graph_store: GraphStore | None = None,
        lineage_store: LineageStore | None = None,
        root_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        storage_root = root_dir if root_dir is not None else Path.cwd()
        self._graph_store = (
            graph_store
            if graph_store is not None
            else GraphStore(root_dir=storage_root)
        )
        self._lineage_store = (
            lineage_store
            if lineage_store is not None
            else LineageStore(root_dir=storage_root)
        )
        self._logger = logger if logger is not None else logging.getLogger(__name__)

    async def validate_fork_request(
        self,
        request: GraphForkRequest,
    ) -> tuple[bool, GraphForkError | None]:
        """Validate that source graph and fork edge exist before forking."""

        seed_error = _validate_custom_seed(request.custom_seed)
        if seed_error is not None:
            return False, seed_error

        try:
            source_graph = self._graph_store.load(request.source_graph_id)
        except FileNotFoundError:
            return (
                False,
                GraphForkError(
                    error=ForkErrorCode.SOURCE_GRAPH_NOT_FOUND,
                    message="source graph does not exist",
                    details={"source_graph_id": request.source_graph_id},
                ),
            )

        edge_reference = _find_edge_reference(
            source_graph.graph_data,
            request.fork_edge_id,
        )
        if edge_reference is None:
            return (
                False,
                GraphForkError(
                    error=ForkErrorCode.EDGE_NOT_FOUND,
                    message="fork edge does not exist in source graph",
                    details={
                        "source_graph_id": request.source_graph_id,
                        "fork_edge_id": request.fork_edge_id,
                    },
                ),
            )

        return True, None

    async def fork_graph(self, request: GraphForkRequest) -> GraphForkResponse:
        """Fork a source graph at a given edge and persist child lineage."""

        started_at = utc_now()
        log_operation(
            self._logger,
            OperationLogEntry(
                operation="fork",
                status="started",
                graph_id=request.source_graph_id,
                started_at=started_at,
                metadata={"fork_edge_id": request.fork_edge_id},
            ),
        )

        is_valid, error = await self.validate_fork_request(request)
        if not is_valid and error is not None:
            log_operation(
                self._logger,
                OperationLogEntry(
                    operation="fork",
                    status="failed",
                    graph_id=request.source_graph_id,
                    started_at=started_at,
                    completed_at=utc_now(),
                    metadata={
                        "error_code": error.error.value,
                        "error_message": error.message,
                        "fork_edge_id": request.fork_edge_id,
                    },
                ),
                level=logging.ERROR,
            )
            raise ValueError(f"{error.error.value}: {error.message}")

        source_graph = self._graph_store.load(request.source_graph_id)
        edge_reference = _find_edge_reference(
            source_graph.graph_data, request.fork_edge_id
        )
        if edge_reference is None:
            raise ValueError("edge disappeared during fork validation")

        copied_graph = _copy_graph_history_up_to_edge(
            source_graph.graph_data,
            edge_reference.source_node_id,
            edge_reference.target_node_id,
        )
        forked_graph_id = str(uuid4())
        created_at = utc_now()
        normalized_custom_seed = _normalize_custom_seed(request.custom_seed)
        seed_config = SeedConfiguration.generate(seed=normalized_custom_seed)
        seed_scope = _build_seed_scope(
            source_graph_id=request.source_graph_id,
            fork_edge_id=request.fork_edge_id,
        )
        fork_metadata = copy.deepcopy(source_graph.metadata)
        fork_metadata.update(
            {
                "seed_numeric_state": seed_config.numeric_state(),
                "seed_scope": seed_scope,
                "seed_scoped_numeric_state": seed_config.scoped_numeric_state(
                    scope=seed_scope
                ),
            }
        )
        fork_point = ForkPoint(
            source_graph_id=request.source_graph_id,
            fork_edge_id=request.fork_edge_id,
            timestamp=created_at,
            label=request.label,
        )
        forked_graph = GraphInstance(
            id=forked_graph_id,
            name=request.label
            if request.label is not None
            else f"{source_graph.name} fork",
            created_at=created_at,
            fork_point=fork_point,
            seed_config=seed_config,
            graph_data=copied_graph,
            metadata=fork_metadata,
            last_modified=created_at,
            state=GraphLifecycleState.ACTIVE,
        )
        self._graph_store.save(forked_graph)

        lineage = _build_lineage(
            lineage_store=self._lineage_store,
            parent_graph_id=source_graph.id,
            child_graph_id=forked_graph.id,
        )
        self._lineage_store.add_lineage(lineage)

        response = GraphForkResponse(
            forked_graph_id=forked_graph.id,
            fork_point=edge_reference,
            seed=seed_config.seed,
            creation_time=created_at,
            parent_graph_id=source_graph.id,
            graph_summary=forked_graph.to_summary(),
        )

        log_operation(
            self._logger,
            OperationLogEntry(
                operation="fork",
                status="success",
                graph_id=forked_graph.id,
                started_at=started_at,
                completed_at=utc_now(),
                metadata={
                    "parent_graph_id": source_graph.id,
                    "fork_edge_id": request.fork_edge_id,
                    "branch_id": lineage.branch_id,
                },
            ),
        )
        return response


def _find_edge_reference(graph: nx.DiGraph, fork_edge_id: str) -> EdgeReference | None:  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    """Return edge node references for a fork edge identifier."""

    for source_node_id, target_node_id, edge_data in graph.edges(data=True):
        if edge_data.get("edge_id") == fork_edge_id:
            return EdgeReference(
                edge_id=fork_edge_id,
                source_node_id=str(source_node_id),
                target_node_id=str(target_node_id),
            )

    return None


def _copy_graph_history_up_to_edge(
    source_graph: nx.DiGraph,  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    source_node_id: str,
    target_node_id: str,
) -> nx.DiGraph:  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    """Deep-copy graph history up to the selected fork edge."""

    history_nodes = set(nx.ancestors(source_graph, target_node_id))
    history_nodes.add(source_node_id)
    history_nodes.add(target_node_id)

    subgraph = source_graph.subgraph(history_nodes).copy()
    copied_graph: nx.DiGraph = nx.DiGraph(subgraph)  # type: ignore[type-arg]  # Runtime NetworkX type is not subscriptable.
    copied_graph.graph = copy.deepcopy(source_graph.graph)
    return copy.deepcopy(copied_graph)


def _build_lineage(
    *,
    lineage_store: LineageStore,
    parent_graph_id: str,
    child_graph_id: str,
) -> GraphLineage:
    """Build the lineage record for a new forked graph."""

    depth = len(lineage_store.get_ancestry(parent_graph_id)) + 1
    return GraphLineage(
        parent_graph_id=parent_graph_id,
        child_graph_id=child_graph_id,
        depth=depth,
        branch_id=f"{parent_graph_id[:8]}-{child_graph_id[:8]}-d{depth}",
    )


def _normalize_custom_seed(custom_seed: str | None) -> str | None:
    """Normalize optional custom seed input for deterministic handling."""

    if custom_seed is None:
        return None

    return custom_seed.strip()


def _build_seed_scope(*, source_graph_id: str, fork_edge_id: str) -> str:
    """Build a deterministic scope key for per-fork seed state."""

    return f"{source_graph_id}:{fork_edge_id}"


def _validate_custom_seed(custom_seed: str | None) -> GraphForkError | None:
    """Validate optional custom seed using contract min/max boundaries."""

    if custom_seed is None:
        return None

    if not isinstance(custom_seed, str):
        return GraphForkError(
            error=ForkErrorCode.INVALID_SEED,
            message="custom seed must be a string",
            details={"custom_seed": str(custom_seed)},
        )

    normalized_seed = custom_seed.strip()
    seed_length = len(normalized_seed)
    if seed_length < CUSTOM_SEED_MIN_LENGTH or seed_length > CUSTOM_SEED_MAX_LENGTH:
        return GraphForkError(
            error=ForkErrorCode.INVALID_SEED,
            message=(
                "custom seed length must be between "
                f"{CUSTOM_SEED_MIN_LENGTH} and {CUSTOM_SEED_MAX_LENGTH}"
            ),
            details={
                "seed_length": seed_length,
                "min_length": CUSTOM_SEED_MIN_LENGTH,
                "max_length": CUSTOM_SEED_MAX_LENGTH,
            },
        )

    return None
