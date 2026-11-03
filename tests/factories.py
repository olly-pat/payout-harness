"""Seeded data factories.

Every test states the shape of the data it needs and nothing else. Nothing
here reads production data, and nothing here is random unless a test asks
for randomness.
"""

from dataclasses import dataclass, field


@dataclass
class ShiftSpec:
    pool_cents: int = 10_000
    weights: dict[str, int] = field(default_factory=lambda: {"ana": 480, "bo": 240, "cleo": 120})


def a_shift(**overrides) -> ShiftSpec:
    return ShiftSpec(**overrides)


def an_even_shift(people: int = 3, pool_cents: int = 9_000) -> ShiftSpec:
    return ShiftSpec(pool_cents=pool_cents, weights={f"e{n}": 60 for n in range(people)})


def an_awkward_shift() -> ShiftSpec:
    """A pool that does not divide cleanly, which is most real shifts."""
    return ShiftSpec(pool_cents=10_001, weights={"ana": 437, "bo": 193, "cleo": 91})
