"""The whole flow, including the worker.

The defect this file exists for: the service reports success and the money
never moves. The only way to see it is to look at the gap between the API
answering and the worker running, so every test here looks at both sides.
"""

import pytest

from tests.factories import a_shift, an_awkward_shift, an_even_shift

pytestmark = pytest.mark.e2e


def test_the_pool_reaches_the_ledger(client, open_shift):
    spec = a_shift(pool_cents=25_000)
    shift_id = open_shift(spec)

    client.post(f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "flow-1"})
    client.post("/_worker/run")

    ledger = client.get(f"/shifts/{shift_id}/ledger").json()
    assert ledger["settled_cents"] == spec.pool_cents
    assert ledger["queue_depth"] == 0


def test_nothing_is_settled_before_the_worker_runs(client, open_shift):
    shift_id = open_shift()

    payout_ids = client.post(
        f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "flow-2"}
    ).json()["payout_ids"]

    before = client.get(f"/shifts/{shift_id}/ledger").json()
    assert before["settled_cents"] == 0
    assert before["queue_depth"] == len(payout_ids)
    for payout_id in payout_ids:
        assert client.get(f"/payouts/{payout_id}").json()["status"] == "pending"


def test_a_settled_payout_has_a_ledger_entry_behind_it(client, open_shift):
    shift_id = open_shift(an_awkward_shift())

    payout_ids = client.post(
        f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "flow-3"}
    ).json()["payout_ids"]
    client.post("/_worker/run")

    settled = sum(
        client.get(f"/payouts/{pid}").json()["amount_cents"]
        for pid in payout_ids
        if client.get(f"/payouts/{pid}").json()["status"] == "settled"
    )
    assert settled == client.get(f"/shifts/{shift_id}/ledger").json()["settled_cents"]


def test_running_the_worker_twice_does_not_pay_twice(client, open_shift):
    spec = an_even_shift(people=4, pool_cents=4_000)
    shift_id = open_shift(spec)

    client.post(f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "flow-4"})
    client.post("/_worker/run")
    client.post("/_worker/run")

    assert client.get(f"/shifts/{shift_id}/ledger").json()["settled_cents"] == spec.pool_cents


def test_two_shifts_do_not_leak_into_each_other(client, open_shift):
    first = open_shift(a_shift(pool_cents=5_000))
    second = open_shift(a_shift(pool_cents=7_000))

    client.post(f"/shifts/{first}/payouts", headers={"Idempotency-Key": "flow-5a"})
    client.post(f"/shifts/{second}/payouts", headers={"Idempotency-Key": "flow-5b"})
    client.post("/_worker/run")

    assert client.get(f"/shifts/{first}/ledger").json()["settled_cents"] == 5_000
    assert client.get(f"/shifts/{second}/ledger").json()["settled_cents"] == 7_000
