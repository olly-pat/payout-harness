"""The API against its own storage, with the worker held still.

Everything here asserts on what the service stored, not on what it answered.
A 202 is a promise, not a payment.
"""

import pytest

from tests.factories import a_shift, an_awkward_shift

pytestmark = pytest.mark.integration


def test_a_payout_request_is_accepted_but_not_yet_paid(client, open_shift):
    shift_id = open_shift(a_shift(pool_cents=10_000))

    response = client.post(f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "req-1"})

    assert response.status_code == 202
    payout_ids = response.json()["payout_ids"]
    assert len(payout_ids) == 3
    for payout_id in payout_ids:
        assert client.get(f"/payouts/{payout_id}").json()["status"] == "pending"
    assert client.get(f"/shifts/{shift_id}/ledger").json()["settled_cents"] == 0


def test_the_shares_add_up_to_the_pool(client, open_shift):
    spec = an_awkward_shift()
    shift_id = open_shift(spec)

    payout_ids = client.post(
        f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "req-2"}
    ).json()["payout_ids"]

    amounts = [client.get(f"/payouts/{pid}").json()["amount_cents"] for pid in payout_ids]
    assert sum(amounts) == spec.pool_cents


def test_a_retried_request_pays_once(client, open_shift):
    shift_id = open_shift()
    headers = {"Idempotency-Key": "req-3"}

    first = client.post(f"/shifts/{shift_id}/payouts", headers=headers).json()["payout_ids"]
    second = client.post(f"/shifts/{shift_id}/payouts", headers=headers).json()["payout_ids"]

    assert first == second
    client.post("/_worker/run")
    ledger = client.get(f"/shifts/{shift_id}/ledger").json()
    assert ledger["settled_cents"] == ledger["pool_cents"]


def test_a_request_without_an_idempotency_key_is_refused(client, open_shift):
    shift_id = open_shift()
    assert client.post(f"/shifts/{shift_id}/payouts").status_code == 422


def test_an_unknown_shift_is_not_invented(client):
    assert client.post("/shifts/nope/payouts", headers={"Idempotency-Key": "x"}).status_code == 404
    assert client.get("/shifts/nope/ledger").status_code == 404
    assert client.get("/payouts/nope").status_code == 404


def test_a_shift_needs_participants(client):
    assert client.post("/shifts", json={"pool_cents": 100, "weights": {}}).status_code == 422
