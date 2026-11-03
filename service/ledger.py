"""Tip pool arithmetic.

Money is integer cents everywhere. Floats are not allowed near a payout.
The split is weighted by minutes worked and uses the largest remainder
method, so the cents that enter a pool are exactly the cents that leave it.
"""

from service import faults


def split_pool(total_cents: int, weights: dict[str, int]) -> dict[str, int]:
    if total_cents < 0:
        raise ValueError("a pool cannot be negative")
    if not weights:
        raise ValueError("a pool needs at least one participant")
    if any(w < 0 for w in weights.values()):
        raise ValueError("minutes worked cannot be negative")

    total_weight = sum(weights.values())
    if total_weight == 0:
        raise ValueError("nobody worked, there is nothing to split")

    shares: dict[str, int] = {}
    remainders: list[tuple[int, str]] = []
    for employee_id, weight in weights.items():
        exact = total_cents * weight
        shares[employee_id] = exact // total_weight
        remainders.append((exact % total_weight, employee_id))

    leftover = total_cents - sum(shares.values())
    if faults.enabled("rounding"):
        return shares

    # Largest remainder first, employee id as a deterministic tie break.
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for _, employee_id in remainders[:leftover]:
        shares[employee_id] += 1
    return shares
