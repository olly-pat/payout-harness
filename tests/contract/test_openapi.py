"""Responses against the schema the service publishes.

A service can answer 200 and still break every client reading it. These tests
validate real responses against the OpenAPI schema the service itself serves,
so the documentation and the behaviour cannot drift apart quietly.
"""

import pytest
from jsonschema import Draft202012Validator

pytestmark = pytest.mark.contract


def _schema_for(spec: dict, path: str, method: str, status: str) -> dict:
    body = spec["paths"][path][method]["responses"][status]["content"]["application/json"]
    resolved = dict(body["schema"])
    resolved["components"] = spec["components"]
    return resolved


def _validate(spec: dict, path: str, method: str, status: str, payload: dict) -> None:
    schema = _schema_for(spec, path, method, status)
    Draft202012Validator(schema).validate(payload)


@pytest.fixture
def spec(client) -> dict:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_every_documented_path_is_reachable(spec, client, open_shift):
    documented = set(spec["paths"])
    assert documented == {
        "/shifts",
        "/shifts/{shift_id}/payouts",
        "/payouts/{payout_id}",
        "/shifts/{shift_id}/ledger",
        "/_worker/run",
    }


def test_the_payout_responses_match_the_published_schema(spec, client, open_shift):
    shift_id = open_shift()
    payouts = client.post(
        f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "contract-1"}
    ).json()
    _validate(spec, "/shifts/{shift_id}/payouts", "post", "202", payouts)

    payout = client.get(f"/payouts/{payouts['payout_ids'][0]}").json()
    _validate(spec, "/payouts/{payout_id}", "get", "200", payout)


def test_the_ledger_response_matches_the_published_schema(spec, client, open_shift):
    shift_id = open_shift()
    ledger = client.get(f"/shifts/{shift_id}/ledger").json()
    _validate(spec, "/shifts/{shift_id}/ledger", "get", "200", ledger)


def test_a_payout_status_is_one_the_clients_know(client, open_shift):
    shift_id = open_shift()
    payout_ids = client.post(
        f"/shifts/{shift_id}/payouts", headers={"Idempotency-Key": "contract-2"}
    ).json()["payout_ids"]

    assert client.get(f"/payouts/{payout_ids[0]}").json()["status"] in {"pending", "settled"}
    client.post("/_worker/run")
    assert client.get(f"/payouts/{payout_ids[0]}").json()["status"] == "settled"
