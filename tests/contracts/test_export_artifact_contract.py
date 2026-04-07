"""Contract tests for export artifact schema and required fields."""

from __future__ import annotations

import pytest

import models

REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "exported_at",
    "session",
    "graph",
    "events",
    "summary",
}

REQUIRED_BLOCK_FIELDS = ("session", "graph", "events", "summary")


def _export_artifact_model() -> type[object] | None:
    return getattr(models, "ExportArtifact", None)


def test_export_artifact_requires_all_top_level_fields() -> None:
    """Export artifacts must expose every required top-level contract field."""

    export_artifact_model = _export_artifact_model()
    model_fields = getattr(export_artifact_model, "model_fields", {})

    assert REQUIRED_TOP_LEVEL_FIELDS.issubset(model_fields), (
        f"missing export artifact fields: {REQUIRED_TOP_LEVEL_FIELDS - set(model_fields)}"
    )


@pytest.mark.parametrize("field_name", REQUIRED_BLOCK_FIELDS)
def test_export_artifact_requires_block(field_name: str) -> None:
    """Export artifacts must require the session, graph, events, and summary blocks."""

    export_artifact_model = _export_artifact_model()
    model_fields = getattr(export_artifact_model, "model_fields", {})
    field = model_fields.get(field_name)

    assert field is not None, f"{field_name} block is required"
    assert field.is_required(), f"{field_name} block must be required"
