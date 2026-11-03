"""A queue that only moves when a test tells it to.

Celery in production, a list here. The point is the same: the API returns
before the money has moved, and a test has to be able to look at the gap.
"""

from collections.abc import Callable


class Queue:
    def __init__(self) -> None:
        self._tasks: list[tuple[str, dict]] = []
        self._handlers: dict[str, Callable[[dict], None]] = {}

    def register(self, name: str, handler: Callable[[dict], None]) -> None:
        self._handlers[name] = handler

    def enqueue(self, name: str, payload: dict) -> None:
        if name not in self._handlers:
            raise KeyError(f"no handler registered for {name}")
        self._tasks.append((name, payload))

    def depth(self) -> int:
        return len(self._tasks)

    def drain(self) -> int:
        processed = 0
        while self._tasks:
            name, payload = self._tasks.pop(0)
            self._handlers[name](payload)
            processed += 1
        return processed
