from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone


LEASE_SECONDS = 180


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
                  lease_expires_at TEXT
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
                       lease_id=NULL, lease_expires_at=NULL
                   WHERE status='running'
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
                       lease_expires_at=NULL, updated_at=?,
                       error='worker lease expired'
                   WHERE status='running'
                     AND (lease_expires_at IS NULL OR lease_expires_at<=?)""",
                (timestamp, timestamp),
            )
            row = connection.execute(
                """SELECT * FROM events
                   WHERE status IN ('queued','retry')
                   ORDER BY created_at
                   LIMIT 1"""
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
            cursor = connection.execute(
                """UPDATE events
                   SET status=?, error=?, updated_at=?,
                       lease_id=NULL, lease_expires_at=NULL
                   WHERE delivery_id=?
                     AND (? IS NULL OR (lease_id=? AND status='running'
                                       AND lease_expires_at>?))""",
                (status, error, now(), delivery_id,
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
