"""The arithmetic layer. Fast, exhaustive, and the only place floats could hide."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from service.ledger import split_pool
from tests.factories import an_awkward_shift

pytestmark = pytest.mark.unit


def test_an_even_pool_splits_evenly():
    assert split_pool(900, {"ana": 60, "bo": 60, "cleo": 60}) == {"ana": 300, "bo": 300, "cleo": 300}


def test_weights_decide_the_share():
    assert split_pool(1200, {"ana": 120, "bo": 60}) == {"ana": 800, "bo": 400}


def test_the_remainder_cents_go_somewhere():
    shares = split_pool(1000, {"ana": 60, "bo": 60, "cleo": 60})
    assert sum(shares.values()) == 1000
    assert sorted(shares.values()) == [333, 333, 334]


def test_an_awkward_pool_is_still_conserved():
    spec = an_awkward_shift()
    assert sum(split_pool(spec.pool_cents, spec.weights).values()) == spec.pool_cents


def test_the_same_pool_always_splits_the_same_way():
    weights = {"ana": 437, "bo": 193, "cleo": 91}
    assert split_pool(10_001, weights) == split_pool(10_001, weights)


@pytest.mark.parametrize(
    "total, weights, reason",
    [
        (-1, {"ana": 60}, "a negative pool"),
        (100, {}, "nobody in the pool"),
        (100, {"ana": -60}, "negative minutes"),
        (100, {"ana": 0}, "nobody worked"),
    ],
)
def test_nonsense_is_refused(total, weights, reason):
    with pytest.raises(ValueError):
        split_pool(total, weights)


@given(
    total=st.integers(min_value=0, max_value=5_000_000),
    weights=st.dictionaries(
        st.text(min_size=1, max_size=6), st.integers(min_value=1, max_value=1440),
        min_size=1, max_size=12,
    ),
)
@settings(max_examples=200, deadline=None)
def test_no_cent_is_created_or_lost(total, weights):
    shares = split_pool(total, weights)
    assert sum(shares.values()) == total
    assert all(amount >= 0 for amount in shares.values())
    assert shares.keys() == weights.keys()
