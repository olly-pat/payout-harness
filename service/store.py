"""Storage. SQLite because the point is the state, not the database."""

import sqlite3
import uuid

SCHEMA = """
CREATE TABLE shifts (id TEXT PRIMARY KEY, pool_cents INTEGER NOT NULL);
CREATE TABLE shift_weights (shift_id TEXT NOT NULL, employee_id TEXT NOT NULL,
    minutes INTEGER NOT NULL, PRIMARY KEY (shift_id, employee_id));
CREATE TABLE payouts (id TEXT PRIMARY KEY, shift_id TEXT NOT NULL,
    employee_id TEXT NOT NULL, amount_cents INTEGER NOT NULL, status TEXT NOT NULL);
CREATE TABLE payout_requests (idempotency_key TEXT PRIMARY KEY, shift_id TEXT NOT NULL,
    payout_ids TEXT NOT NULL);
CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, payout_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL);
"""


class Store:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def create_shift(self, pool_cents: int, weights: dict[str, int]) -> str:
        shift_id = uuid.uuid4().hex[:12]
        with self.db:
            self.db.execute("INSERT INTO shifts VALUES (?, ?)", (shift_id, pool_cents))
            self.db.executemany(
                "INSERT INTO shift_weights VALUES (?, ?, ?)",
                [(shift_id, employee, minutes) for employee, minutes in weights.items()],
            )
        return shift_id

    def shift(self, shift_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,)).fetchone()

    def weights(self, shift_id: str) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT employee_id, minutes FROM shift_weights WHERE shift_id = ?", (shift_id,)
        ).fetchall()
        return {row["employee_id"]: row["minutes"] for row in rows}

    def add_payouts(self, shift_id: str, shares: dict[str, int], status: str) -> list[str]:
        rows = [
            (uuid.uuid4().hex[:12], shift_id, employee, amount, status)
            for employee, amount in sorted(shares.items())
        ]
        with self.db:
            self.db.executemany("INSERT INTO payouts VALUES (?, ?, ?, ?, ?)", rows)
        return [row[0] for row in rows]

    def payout(self, payout_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM payouts WHERE id = ?", (payout_id,)).fetchone()

    def mark_settled(self, payout_id: str) -> None:
        with self.db:
            self.db.execute("UPDATE payouts SET status = 'settled' WHERE id = ?", (payout_id,))

    def write_ledger(self, payout_id: str, amount_cents: int) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO ledger (payout_id, amount_cents) VALUES (?, ?)",
                (payout_id, amount_cents),
            )

    def settled_cents(self, shift_id: str) -> int:
        row = self.db.execute(
            "SELECT COALESCE(SUM(l.amount_cents), 0) AS total FROM ledger l "
            "JOIN payouts p ON p.id = l.payout_id WHERE p.shift_id = ?",
            (shift_id,),
        ).fetchone()
        return int(row["total"])

    def remember_request(self, key: str, shift_id: str, payout_ids: list[str]) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO payout_requests VALUES (?, ?, ?)",
                (key, shift_id, ",".join(payout_ids)),
            )

    def recall_request(self, key: str) -> list[str] | None:
        row = self.db.execute(
            "SELECT payout_ids FROM payout_requests WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return row["payout_ids"].split(",") if row else None
