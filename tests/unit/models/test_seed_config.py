"""Tests for the SeedConfiguration model."""

from __future__ import annotations

import string

import pytest
from pydantic import ValidationError

from models.seed_config import SeedAlgorithm, SeedConfiguration


def test_seed_configuration_generate_keeps_user_seed() -> None:
    """Generating with a user seed should preserve the supplied value."""

    seed_config = SeedConfiguration.generate(seed="narrative_variant_a")

    assert seed_config.seed == "narrative_variant_a"
    assert seed_config.algorithm is SeedAlgorithm.PYTHON_HASH
    assert seed_config.deterministic is True


def test_seed_configuration_generate_creates_alphanumeric_seed() -> None:
    """Generating without a seed should create a 16-character alphanumeric seed."""

    seed_config = SeedConfiguration.generate()

    assert len(seed_config.seed) == 16
    assert all(
        character in string.ascii_letters + string.digits
        for character in seed_config.seed
    )
    assert seed_config.deterministic is True


def test_seed_configuration_rejects_nondeterministic_mode() -> None:
    """Fork seed settings must always be deterministic."""

    with pytest.raises(ValidationError):
        SeedConfiguration(
            seed="custom",
            algorithm=SeedAlgorithm.SHA256,
            deterministic=False,
        )
