"""Deliberate defects, switched on from the environment.

The suite is supposed to catch each of these. CI runs the tests twice: once
with a clean service, which must pass, and once per fault, which must fail.
A test suite that cannot fail is not a gate, it is decoration.
"""

import os

KNOWN = {
    "rounding": "pool split drops the remainder cents",
    "ghost_success": "payout is marked paid before the ledger entry exists",
    "double_pay": "the idempotency key is ignored on retry",
}


def active() -> set[str]:
    raw = os.environ.get("PAYOUT_FAULTS", "")
    names = {name.strip() for name in raw.split(",") if name.strip()}
    unknown = names - KNOWN.keys()
    if unknown:
        raise ValueError(f"unknown faults: {sorted(unknown)}")
    return names


def enabled(name: str) -> bool:
    if name not in KNOWN:
        raise ValueError(f"unknown fault: {name}")
    return name in active()
