import pytest
from fastapi.testclient import TestClient

from service.app import create_app
from service.queue import Queue
from service.store import Store
from tests.factories import ShiftSpec, a_shift


@pytest.fixture
def queue() -> Queue:
    return Queue()


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def client(store: Store, queue: Queue) -> TestClient:
    """A service with its own storage and its own queue, per test."""
    return TestClient(create_app(store=store, queue=queue))


@pytest.fixture
def open_shift(client: TestClient):
    def _open(spec: ShiftSpec | None = None) -> str:
        spec = spec or a_shift()
        response = client.post(
            "/shifts", json={"pool_cents": spec.pool_cents, "weights": spec.weights}
        )
        assert response.status_code == 201, response.text
        return response.json()["shift_id"]

    return _open
