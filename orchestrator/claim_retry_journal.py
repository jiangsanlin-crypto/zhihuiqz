"""Host-local durable acquisition attempts. Never stores tokens or error bodies."""
import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class ClaimRetriesExhausted(RuntimeError):
    pass


class ClaimRetryJournal:
    def __init__(self, path):
        self.path = str(Path(path))
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS acquisition_attempts(
                worker TEXT, request TEXT, binding_hash TEXT, attempt INTEGER,
                status TEXT, error_code TEXT, updated_at TEXT,
                PRIMARY KEY(worker,request,attempt))''')
            db.commit()

    @staticmethod
    def identity(binding):
        return hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()

    def attempts(self, binding, worker, request):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(row) for row in db.execute(
                'SELECT * FROM acquisition_attempts WHERE worker=? AND request=? ORDER BY attempt', (worker, request))]
        if any(row['binding_hash'] != self.identity(binding) for row in rows):
            raise ValueError('acquisition request cannot change binding')
        return rows

    def record(self, binding, worker, request, attempt, status, error_code=''):
        # Enumerated codes only: exception text may contain credentials or URLs.
        if status not in {'attempting','retryable','exhausted','stale','acquired'}:
            raise ValueError('invalid acquisition status')
        if error_code not in {'','TRANSPORT','HTTP_RETRYABLE','STATE_OR_AUTH','WORKER_ACQUISITION_FAILED'}:
            raise ValueError('invalid acquisition error code')
        identity = self.identity(binding)
        with closing(sqlite3.connect(self.path, timeout=30)) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT binding_hash FROM acquisition_attempts WHERE worker=? AND request=? LIMIT 1',
                             (worker,request)).fetchone()
            if row and row[0] != identity:
                raise ValueError('acquisition request cannot change binding')
            db.execute('''INSERT INTO acquisition_attempts VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(worker,request,attempt) DO UPDATE SET
                status=excluded.status,error_code=excluded.error_code,updated_at=excluded.updated_at''',
                (worker,request,identity,attempt,status,error_code,datetime.now(timezone.utc).isoformat()))
            db.commit()

    def next_request(self, binding, worker, *, timestamp=None):
        """Called only after fresh READY discovery; cooldown is not CI evidence."""
        timestamp = timestamp or datetime.now(timezone.utc)
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("""SELECT * FROM acquisition_attempts WHERE worker=? AND binding_hash=?
                ORDER BY updated_at DESC,attempt DESC LIMIT 1""",
                (worker,self.identity(binding))).fetchone()
        if row:
            if row['status'] in {'attempting','retryable'}:
                return row['request']
            if row['status'] in {'exhausted','stale'}:
                elapsed = (timestamp - datetime.fromisoformat(row['updated_at'])).total_seconds()
                if elapsed < 600:
                    return None
        return str(uuid.uuid4())
