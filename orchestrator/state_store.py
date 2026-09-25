from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """Durable single-orchestrator event queue.

    SQLite is local to one orchestrator deployment. If the process exits while
    an event is marked running, no live worker can still own that lease. On the
    next process start we therefore return such events to retry, preserving the
    attempt counter and exact original delivery payload.
    """

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.lock = threading.Lock()
        self._init()
        self.recover_interrupted()

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
                  checkpoint_json TEXT
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

    def recover_interrupted(self) -> int:
        """Requeue events left running by a previous process instance."""
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
                       updated_at=?
                   WHERE status='running'""",
                (timestamp,),
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
            row = connection.execute(
                """SELECT * FROM events
                   WHERE status IN ('queued','retry')
                   ORDER BY created_at
                   LIMIT 1"""
            ).fetchone()
            if not row:
                connection.execute("COMMIT")
                return None

            connection.execute(
                """UPDATE events
                   SET status='running', attempts=attempts+1, updated_at=?
                   WHERE delivery_id=?""",
                (now(), row["delivery_id"]),
            )
            connection.execute("COMMIT")
            return {
                "delivery_id": row["delivery_id"],
                "event_name": row["event_name"],
                "payload": json.loads(row["payload_json"]),
                "attempts": row["attempts"] + 1,
                "checkpoint": (
                    json.loads(row["checkpoint_json"])
                    if row["checkpoint_json"]
                    else None
                ),
            }

    def checkpoint(self, delivery_id: str, payload: dict) -> None:
        """Persist replay data before an external branch mutation."""
        with self.lock, self.conn() as connection:
            connection.execute(
                """UPDATE events
                   SET checkpoint_json=?, updated_at=?
                   WHERE delivery_id=?""",
                (json.dumps(payload), now(), delivery_id),
            )

    def finish(
        self,
        delivery_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        with self.lock, self.conn() as connection:
            connection.execute(
                """UPDATE events
                   SET status=?, error=?, updated_at=?
                   WHERE delivery_id=?""",
                (status, error, now(), delivery_id),
            )

    def get(self, delivery_id: str) -> dict | None:
        with self.lock, self.conn() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE delivery_id=?",
                (delivery_id,),
            ).fetchone()
        return dict(row) if row else None
