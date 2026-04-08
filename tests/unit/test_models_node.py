"""Tests for scene node activation metadata and drift state."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from models.common import DriftCategory, NodeKind
from models.node import SceneNode
from utils.time import utc_now


def test_scene_node_rejects_seed_protected_non_seed_nodes() -> None:
    """Only seed nodes may be marked as seed protected."""

    with pytest.raises(ValidationError):
        SceneNode(
            node_id="scene-1",
            session_id=UUID(int=1),
            node_kind=NodeKind.SCENE,
            text="scene",
            is_seed_protected=True,
        )


def test_scene_node_requires_activation_metadata_consistency() -> None:
    """Activation count and activation timestamp must be synchronized."""

    with pytest.raises(ValidationError):
        SceneNode(
            node_id="scene-1",
            session_id=UUID(int=1),
            node_kind=NodeKind.SCENE,
            text="scene",
            activation_count=0,
            last_activated_at=utc_now(),
        )

    with pytest.raises(ValidationError):
        SceneNode(
            node_id="scene-2",
            session_id=UUID(int=1),
            node_kind=NodeKind.SCENE,
            text="scene",
            activation_count=1,
        )


def test_scene_node_activate_updates_timestamp_and_drift_category() -> None:
    """Activation should increment count and derive drift from entropy."""

    node = SceneNode(
        node_id="scene-1",
        session_id=UUID(int=1),
        node_kind=NodeKind.SCENE,
        text="scene",
        entropy_score=0.8,
    )

    node.activate(activated_at=datetime(2026, 4, 7, tzinfo=timezone.utc))

    assert node.activation_count == 1
    assert node.last_activated_at == datetime(2026, 4, 7, tzinfo=timezone.utc)
    assert node.drift_category is DriftCategory.CRITICAL


def test_scene_node_derives_volatile_drift_band() -> None:
    """Entropy values in the third band should be marked volatile."""

    node = SceneNode(
        node_id="scene-1",
        session_id=UUID(int=1),
        node_kind=NodeKind.SCENE,
        text="scene",
        entropy_score=0.7,
    )

    assert node.drift_category is DriftCategory.VOLATILE
