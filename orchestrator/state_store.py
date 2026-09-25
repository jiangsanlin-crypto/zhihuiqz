from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone


LEASE_SECONDS = 180
RETRY_DELAYS_SECONDS = (0, 120, 300, 600, 1200)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """Durable single-orchestrator event queue.

    SQLite claims are fenced by a renewable lease. A second process sharing
    this database must never reclaim a live worker on startup.
    """

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.lock = threading.Lock()
        self._init()

    def conn(self):
        connection = sqlite3.connect(
            self.path,
            timeout=30,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self.conn() as connection:
            connection.executescript(
                """PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events(
                  delivery_id TEXT PRIMARY KEY,
                  event_name TEXT,
                  payload_json TEXT,
                  status TEXT DEFAULT 'queued',
                  attempts INTEGER DEFAULT 0,
                  error TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  checkpoint_json TEXT,
                  lease_id TEXT,
                  lease_expires_at TEXT,
                  next_retry_at TEXT
                );
                CREATE TABLE IF NOT EXISTS operation_claims(
                  operation_key TEXT PRIMARY KEY,
                  delivery_id TEXT NOT NULL,
                  lease_id TEXT NOT NULL,
                  claimed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recovery_audit(
                  event_id TEXT PRIMARY KEY,
                  delivery_id TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );"""
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(events)")
            }
            if "checkpoint_json" not in columns:
                connection.execute(
                    "ALTER TABLE events ADD COLUMN checkpoint_json TEXT"
                )
            if "lease_id" not in columns:
                connection.execute("ALTER TABLE events ADD COLUMN lease_id TEXT")
            if "lease_expires_at" not in columns:
                connection.execute(
                    "ALTER TABLE events ADD COLUMN lease_expires_at TEXT"
                )
            if "next_retry_at" not in columns:
                connection.execute(
                    "ALTER TABLE events ADD COLUMN next_retry_at TEXT"
                )

    def recover_interrupted(self) -> int:
        """Requeue only expired (or pre-migration unleased) events."""
        timestamp = now()
        with self.lock, self.conn() as connection:
            cursor = connection.execute(
                """UPDATE events
                   SET status='retry',
                       error=CASE
                         WHEN error IS NULL OR error=''
                         THEN 'recovered after orchestrator restart'
                         ELSE error || '; recovered after orchestrator restart'
                       END,
                       updated_at=?,
                       lease_id=NULL, lease_expires_at=NULL,
                       next_retry_at=NULL
                   WHERE status='running' AND event_name!='external_claim'
                     AND (lease_expires_at IS NULL OR lease_expires_at<=?)""",
                (timestamp, timestamp),
            )
            return cursor.rowcount

    def enqueue(self, delivery_id: str, event: str, payload: dict) -> bool:
        timestamp = now()
        with self.lock, self.conn() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO events(
                     delivery_id,event_name,payload_json,status,attempts,
                     created_at,updated_at
                   )
                   VALUES(?,?,?,'queued',0,?,?)""",
                (
                    delivery_id,
                    event,
                    json.dumps(payload),
                    timestamp,
                    timestamp,
                ),
            )
            return cursor.rowcount == 1

    def claim_next(self):
        with self.lock, self.conn() as connection:
            connection.execute("BEGIN IMMEDIATE")
            timestamp = now()
            connection.execute(
                """UPDATE events SET status='retry', lease_id=NULL,
                       lease_expires_at=NULL, next_retry_at=NULL, updated_at=?,
                       error='worker lease expired'
                   WHERE status='running' AND event_name!='external_claim'
                     AND (lease_expires_at IS NULL OR lease_expires_at<=?)""",
                (timestamp, timestamp),
            )
            row = connection.execute(
                """SELECT * FROM events
                   WHERE status='queued'
                      OR (status='retry'
                          AND (next_retry_at IS NULL OR next_retry_at<=?))
                   ORDER BY created_at
                   LIMIT 1""",
                (timestamp,),
            ).fetchone()
            if not row:
                connection.execute("COMMIT")
                return None

            lease_id = str(uuid.uuid4())
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)
            ).isoformat()
            connection.execute(
                """UPDATE events
                   SET status='running', attempts=attempts+1, updated_at=?,
                       lease_id=?, lease_expires_at=?
                   WHERE delivery_id=?""",
                (timestamp, lease_id, expires_at, row["delivery_id"]),
            )
            connection.execute("COMMIT")
            return {
                "delivery_id": row["delivery_id"],
                "event_name": row["event_name"],
                "payload": json.loads(row["payload_json"]),
                "attempts": row["attempts"] + 1,
                "lease_id": lease_id,
                "checkpoint": (
                    json.loads(row["checkpoint_json"])
                    if row["checkpoint_json"] else None
                ),
            }

    def heartbeat(self, delivery_id: str, lease_id: str) -> bool:
        with self.lock, self.conn() as connection:
            timestamp = now()
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)
            ).isoformat()
            return connection.execute(
                """UPDATE events SET lease_expires_at=?, updated_at=?
                   WHERE delivery_id=? AND lease_id=? AND status='running'
                     AND lease_expires_at>?""",
                (expires_at, timestamp, delivery_id, lease_id, timestamp),
            ).rowcount == 1

    def claim_operation(self, operation_key: str, delivery_id: str, lease_id: str) -> bool:
        """Fence duplicate deliveries for one repo/PR/SHA/phase in this DB.

        The owning event's renewable lease is authoritative. A second process
        sharing this database cannot acquire the operation until that lease
        expires or the event reaches a terminal state.
        """
        with self.lock, self.conn() as connection:
            connection.execute("BEGIN IMMEDIATE")
            timestamp = now()
            own = connection.execute(
                """SELECT 1 FROM events WHERE delivery_id=? AND lease_id=?
                   AND status='running' AND lease_expires_at>?""",
                (delivery_id, lease_id, timestamp),
            ).fetchone()
            if own is None:
                raise RuntimeError("WORKER_LEASE_LOST")
            active = connection.execute(
                """SELECT c.delivery_id, c.lease_id FROM operation_claims c
                   JOIN events e ON e.delivery_id=c.delivery_id AND e.lease_id=c.lease_id
                   WHERE c.operation_key=? AND e.status='running'
                     AND e.lease_expires_at>?""",
                (operation_key, timestamp),
            ).fetchone()
            if active is not None:
                owned = active["delivery_id"] == delivery_id and active["lease_id"] == lease_id
                connection.execute("COMMIT")
                return owned
            connection.execute(
                """INSERT INTO operation_claims(operation_key,delivery_id,lease_id,claimed_at)
                   VALUES(?,?,?,?) ON CONFLICT(operation_key) DO UPDATE SET
                     delivery_id=excluded.delivery_id, lease_id=excluded.lease_id,
                     claimed_at=excluded.claimed_at""",
                (operation_key, delivery_id, lease_id, timestamp),
            )
            connection.execute("COMMIT")
            return True

    def assert_operation(self, operation_key: str, delivery_id: str, lease_id: str) -> None:
        with self.lock, self.conn() as connection:
            row = connection.execute(
                """SELECT 1 FROM operation_claims c JOIN events e
                   ON e.delivery_id=c.delivery_id AND e.lease_id=c.lease_id
                   WHERE c.operation_key=? AND c.delivery_id=? AND c.lease_id=?
                     AND e.status='running' AND e.lease_expires_at>?""",
                (operation_key, delivery_id, lease_id, now()),
            ).fetchone()
        if row is None:
            raise RuntimeError("WORKER_OPERATION_LEASE_LOST")

    @staticmethod
    def external_delivery_id(worker_id: str, request_id: str) -> str:
        value = json.dumps([worker_id, request_id], separators=(",", ":"))
        return "external:" + hashlib.sha256(value.encode()).hexdigest()

    def claim_external(self, binding: dict, worker_id: str, request_id: str) -> dict:
        """Acquire the same operation lock without enqueueing a runner event."""
        delivery_id = self.external_delivery_id(worker_id, request_id)
        payload = dict(binding, worker_id=worker_id)
        with self.lock, self.conn() as connection:
            connection.execute("BEGIN IMMEDIATE")
            timestamp = now()
            existing = connection.execute(
                "SELECT * FROM events WHERE delivery_id=?", (delivery_id,),
            ).fetchone()
            active = connection.execute(
                """SELECT c.delivery_id,c.lease_id FROM operation_claims c JOIN events e
                   ON e.delivery_id=c.delivery_id AND e.lease_id=c.lease_id
                   WHERE c.operation_key=? AND e.status='running' AND e.lease_expires_at>?""",
                (binding["operation_key"], timestamp),
            ).fetchone()
            if existing:
                if json.loads(existing["payload_json"]) != payload:
                    raise RuntimeError("CLAIM_REQUEST_REUSED")
                if (existing["status"] != "running" or not existing["lease_expires_at"]
                    or existing["lease_expires_at"] <= timestamp or active is None
                    or active["delivery_id"] != delivery_id
                    or active["lease_id"] != existing["lease_id"]):
                    raise RuntimeError("WORKER_LEASE_LOST")
                connection.execute("COMMIT")
                return dict(existing)
            if active is not None:
                raise RuntimeError("ANOTHER_WORKER_OWNS_LEASE")
            lease_id = str(uuid.uuid4())
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)).isoformat()
            connection.execute(
                """INSERT INTO events(delivery_id,event_name,payload_json,status,attempts,
                   created_at,updated_at,lease_id,lease_expires_at)
                   VALUES(?,'external_claim',?,'running',1,?,?,?,?)""",
                (delivery_id, json.dumps(payload), timestamp, timestamp, lease_id, expires_at),
            )
            connection.execute(
                """INSERT INTO operation_claims(operation_key,delivery_id,lease_id,claimed_at)
                   VALUES(?,?,?,?) ON CONFLICT(operation_key) DO UPDATE SET
                   delivery_id=excluded.delivery_id,lease_id=excluded.lease_id,
                   claimed_at=excluded.claimed_at""",
                (binding["operation_key"], delivery_id, lease_id, timestamp),
            )
            row = connection.execute("SELECT * FROM events WHERE delivery_id=?", (delivery_id,)).fetchone()
            connection.execute("COMMIT")
            return dict(row)

    def assert_lease(self, delivery_id: str, lease_id: str) -> None:
        with self.lock, self.conn() as connection:
            row = connection.execute(
                """SELECT 1 FROM events WHERE delivery_id=? AND lease_id=?
                     AND status='running' AND lease_expires_at>?""",
                (delivery_id, lease_id, now()),
            ).fetchone()
        if row is None:
            raise RuntimeError("WORKER_LEASE_LOST")

    def checkpoint(self, delivery_id: str, payload: dict, lease_id: str | None = None) -> None:
        """Persist replay data before an external branch mutation."""
        with self.lock, self.conn() as connection:
            cursor = connection.execute(
                """UPDATE events SET checkpoint_json=?, updated_at=?
                   WHERE delivery_id=? AND status='running'
                     AND (? IS NULL OR (lease_id=? AND lease_expires_at>?))""",
                (json.dumps(payload), now(), delivery_id,
                 lease_id, lease_id, now()),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("WORKER_LEASE_LOST")

    def finish(
        self,
        delivery_id: str,
        status: str,
        error: str | None = None,
        lease_id: str | None = None,
    ) -> bool:
        with self.lock, self.conn() as connection:
            row = connection.execute(
                "SELECT attempts FROM events WHERE delivery_id=?",
                (delivery_id,),
            ).fetchone()
            delay = RETRY_DELAYS_SECONDS[min(max((row["attempts"] if row else 1) - 1, 0), 4)]
            next_retry_at = (
                datetime.now(timezone.utc) + timedelta(seconds=delay)
            ).isoformat() if status == "retry" else None
            cursor = connection.execute(
                """UPDATE events
                   SET status=?, error=?, updated_at=?,
                       lease_id=NULL, lease_expires_at=NULL, next_retry_at=?
                   WHERE delivery_id=?
                     AND (? IS NULL OR (lease_id=? AND status='running'
                                       AND lease_expires_at>?))""",
                (status, error, now(), next_retry_at, delivery_id,
                 lease_id, lease_id, now()),
            )
            return cursor.rowcount == 1

    def get(self, delivery_id: str) -> dict | None:
        with self.lock, self.conn() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE delivery_id=?",
                (delivery_id,),
            ).fetchone()
        return dict(row) if row else None

    def record_recovery_audit(self, delivery_id: str, audit: dict) -> None:
        identity = [delivery_id, audit["lease_id"], audit["evidence_generation"], audit["status"]]
        event_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        with self.lock, self.conn() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO recovery_audit(event_id,delivery_id,payload_json,created_at)
                   VALUES(?,?,?,?)""", (event_id, delivery_id, json.dumps(audit), now()),
            )
