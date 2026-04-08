"""Seed configuration model for deterministic graph behavior."""

from __future__ import annotations

import hashlib
import secrets
import string
from enum import StrEnum

from pydantic import StringConstraints, model_validator
from typing_extensions import Annotated

from models.common import StrictBaseModel

__all__ = [
    "SEED_AUTO_GENERATED_LENGTH",
    "SeedAlgorithm",
    "SeedConfiguration",
    "seed_to_numeric_state",
]

SEED_AUTO_GENERATED_LENGTH = 16

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
    algorithm: SeedAlgorithm = SeedAlgorithm.SHA256
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
        return cls(seed=generated_seed, algorithm=SeedAlgorithm.SHA256)

    def numeric_state(self) -> int:
        """Return deterministic numeric RNG state derived from the seed text."""

        return seed_to_numeric_state(self.seed)

    def scoped_numeric_state(self, *, scope: str) -> int:
        """Return deterministic numeric state scoped to a graph fork context."""

        return seed_to_numeric_state(f"{self.seed}:{scope}")


def seed_to_numeric_state(seed_text: str) -> int:
    """Derive a stable unsigned 64-bit integer state from seed text."""

    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _generate_random_seed(length: int = SEED_AUTO_GENERATED_LENGTH) -> str:
    """Generate an alphanumeric seed string suitable for deterministic replay."""

    population = string.ascii_letters + string.digits
    return "".join(secrets.choice(population) for _ in range(length))
