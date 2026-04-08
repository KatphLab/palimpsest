"""Seed configuration model for deterministic graph behavior."""

from __future__ import annotations

import secrets
import string
from enum import StrEnum

from pydantic import StringConstraints, model_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel

__all__ = ["SeedAlgorithm", "SeedConfiguration"]

_SeedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class SeedAlgorithm(StrEnum):
    """Supported deterministic seed transformation algorithms."""

    PYTHON_HASH = "python_hash"
    SHA256 = "sha256"


class SeedConfiguration(StrictBaseModel):
    """Seed settings for forked graph generation."""

    seed: _SeedText
    algorithm: SeedAlgorithm = SeedAlgorithm.PYTHON_HASH
    deterministic: bool = True

    @model_validator(mode="after")
    def _validate_deterministic(self) -> SeedConfiguration:
        if not self.deterministic:
            raise ValueError("deterministic must be true for forked graphs")

        return self

    @classmethod
    def generate(cls, *, seed: str | None = None) -> SeedConfiguration:
        """Create deterministic seed configuration from user or generated seed."""

        generated_seed = seed if seed is not None else _generate_random_seed()
        return cls(seed=generated_seed, algorithm=SeedAlgorithm.PYTHON_HASH)


def _generate_random_seed(length: int = 16) -> str:
    """Generate an alphanumeric seed string suitable for deterministic replay."""

    population = string.ascii_letters + string.digits
    return "".join(secrets.choice(population) for _ in range(length))
