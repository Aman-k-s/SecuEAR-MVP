"""
SQLite access layer for SecuEAR.

Deliberately plain sqlite3 (per the project's locked stack decision) - no ORM.
Each function opens and closes its own short-lived connection, which is fine
at this MVP's scale (single-file DB, low concurrency demo usage) and keeps
things simple to read end-to-end.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    embedding     TEXT NOT NULL,      -- JSON-serialized float array (L2-normalized)
    enrolled_side TEXT NOT NULL CHECK (enrolled_side IN ('left', 'right')),
    enrolled_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallets (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id),
    balance REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    txn_ref         TEXT,
    event_type      TEXT NOT NULL CHECK (event_type IN ('enroll', 'verify', 'payment', 'recharge')),
    match_score     REAL,
    high_threshold  REAL,
    med_threshold   REAL,
    decision_tier   TEXT,             -- 'auto_approve' | 'pin_required' | 'deny' | NULL for enroll/recharge
    comparison_mode TEXT,             -- 'same_side' | 'mirrored_cross_side' | NULL
    reasoning       TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_ref       TEXT NOT NULL,
    mock_order_id TEXT NOT NULL,
    amount        REAL NOT NULL,
    status        TEXT NOT NULL,      -- 'pending_pin' | 'captured' | 'denied' | 'failed'
    created_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# --- users / embeddings --------------------------------------------------

def create_user(user_id: str, name: str, embedding: list, side: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, name, embedding, enrolled_side, enrolled_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, name, json.dumps(embedding), side, _now()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)",
            (user_id,),
        )


def get_user(user_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def get_user_embedding(user_id: str) -> Optional[tuple]:
    """Returns (embedding: list[float], side: str) or None."""
    row = get_user(user_id)
    if row is None:
        return None
    return json.loads(row["embedding"]), row["enrolled_side"]


# --- wallets ---------------------------------------------------------------

def get_balance(user_id: str) -> Optional[float]:
    with get_conn() as conn:
        row = conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        return row["balance"] if row else None


def credit_wallet(user_id: str, amount: float) -> float:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO wallets (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance",
            (user_id, amount),
        )
        return conn.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()["balance"]


def debit_wallet(user_id: str, amount: float) -> float:
    with get_conn() as conn:
        conn.execute(
            "UPDATE wallets SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id),
        )
        return conn.execute(
            "SELECT balance FROM wallets WHERE user_id = ?", (user_id,)
        ).fetchone()["balance"]


# --- audit log ---------------------------------------------------------------

def log_event(
    user_id: str,
    event_type: str,
    reasoning: str,
    txn_ref: Optional[str] = None,
    match_score: Optional[float] = None,
    high_threshold: Optional[float] = None,
    med_threshold: Optional[float] = None,
    decision_tier: Optional[str] = None,
    comparison_mode: Optional[str] = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO audit_log "
            "(user_id, txn_ref, event_type, match_score, high_threshold, med_threshold, "
            " decision_tier, comparison_mode, reasoning, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id, txn_ref, event_type, match_score, high_threshold, med_threshold,
                decision_tier, comparison_mode, reasoning, _now(),
            ),
        )
        return cur.lastrowid


def get_audit_log(limit: int = 100) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# --- payments ---------------------------------------------------------------

def record_payment(txn_ref: str, mock_order_id: str, amount: float, status: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO payments (txn_ref, mock_order_id, amount, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (txn_ref, mock_order_id, amount, status, _now()),
        )
        return cur.lastrowid


def update_payment_status(txn_ref: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE payments SET status = ? WHERE txn_ref = ? "
            "AND id = (SELECT id FROM payments WHERE txn_ref = ? ORDER BY id DESC LIMIT 1)",
            (status, txn_ref, txn_ref),
        )


def get_latest_payment(txn_ref: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM payments WHERE txn_ref = ? ORDER BY id DESC LIMIT 1", (txn_ref,)
        ).fetchone()
