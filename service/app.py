"""A small tip payout service, so the tests have something real to run against.

The flow it models is the one that matters in a tips platform: a shift closes,
the pool is split between the people who worked it, and the money moves
asynchronously. The API answers before the ledger has been written, which is
exactly where the interesting defects live.
"""

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from service import faults
from service.ledger import split_pool
from service.queue import Queue
from service.store import Store


class ShiftIn(BaseModel):
    pool_cents: int = Field(ge=0)
    weights: dict[str, int]


class ShiftOut(BaseModel):
    shift_id: str


class PayoutsOut(BaseModel):
    payout_ids: list[str]


class PayoutOut(BaseModel):
    id: str
    shift_id: str
    employee_id: str
    amount_cents: int
    status: str


class LedgerOut(BaseModel):
    shift_id: str
    pool_cents: int
    settled_cents: int
    queue_depth: int


def create_app(store: Store | None = None, queue: Queue | None = None) -> FastAPI:
    store = store or Store()
    queue = queue or Queue()

    def settle(payload: dict) -> None:
        payout = store.payout(payload["payout_id"])
        if payout is None:
            raise KeyError(payload["payout_id"])
        store.write_ledger(payout["id"], payout["amount_cents"])
        store.mark_settled(payout["id"])

    queue.register("settle", settle)

    app = FastAPI(title="payout-harness service", version="1.0.0")
    app.state.store = store
    app.state.queue = queue

    @app.post("/shifts", response_model=ShiftOut, status_code=201)
    def create_shift(body: ShiftIn) -> ShiftOut:
        if not body.weights:
            raise HTTPException(422, "a shift needs at least one participant")
        return ShiftOut(shift_id=store.create_shift(body.pool_cents, body.weights))

    @app.post("/shifts/{shift_id}/payouts", response_model=PayoutsOut, status_code=202)
    def request_payouts(
        shift_id: str, idempotency_key: str = Header(alias="Idempotency-Key")
    ) -> PayoutsOut:
        shift = store.shift(shift_id)
        if shift is None:
            raise HTTPException(404, "no such shift")

        if not faults.enabled("double_pay"):
            already = store.recall_request(idempotency_key)
            if already is not None:
                return PayoutsOut(payout_ids=already)

        shares = split_pool(shift["pool_cents"], store.weights(shift_id))
        status = "settled" if faults.enabled("ghost_success") else "pending"
        payout_ids = store.add_payouts(shift_id, shares, status)
        for payout_id in payout_ids:
            queue.enqueue("settle", {"payout_id": payout_id})
        if not faults.enabled("double_pay"):
            store.remember_request(idempotency_key, shift_id, payout_ids)
        return PayoutsOut(payout_ids=payout_ids)

    @app.get("/payouts/{payout_id}", response_model=PayoutOut)
    def read_payout(payout_id: str) -> PayoutOut:
        row = store.payout(payout_id)
        if row is None:
            raise HTTPException(404, "no such payout")
        return PayoutOut(**dict(row))

    @app.get("/shifts/{shift_id}/ledger", response_model=LedgerOut)
    def read_ledger(shift_id: str) -> LedgerOut:
        shift = store.shift(shift_id)
        if shift is None:
            raise HTTPException(404, "no such shift")
        return LedgerOut(
            shift_id=shift_id,
            pool_cents=shift["pool_cents"],
            settled_cents=store.settled_cents(shift_id),
            queue_depth=queue.depth(),
        )

    @app.post("/_worker/run")
    def run_worker() -> dict[str, int]:
        """Stands in for the Celery worker. Tests decide when the money moves."""
        return {"processed": queue.drain()}

    return app
