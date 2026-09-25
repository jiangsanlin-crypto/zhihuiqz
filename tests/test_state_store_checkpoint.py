from __future__ import annotations

import sqlite3

from orchestrator.state_store import StateStore


def test_checkpoint_survives_retry(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    assert store.enqueue("delivery-1", "repository_dispatch", {"value": 1})

    first = store.claim_next()
    assert first["checkpoint"] is None
    store.checkpoint(
        "delivery-1",
        {
            "source_sha": "old",
            "result": {"status": "success", "summary": "done"},
        },
    )
    store.finish("delivery-1", "retry", "simulated crash")

    resumed = store.claim_next()
    assert resumed["checkpoint"]["source_sha"] == "old"
    assert resumed["checkpoint"]["result"]["status"] == "success"


def test_existing_database_is_migrated_for_checkpoints(tmp_path):
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """CREATE TABLE events(
          delivery_id TEXT PRIMARY KEY,
          event_name TEXT,
          payload_json TEXT,
          status TEXT DEFAULT 'queued',
          attempts INTEGER DEFAULT 0,
          error TEXT,
          created_at TEXT,
          updated_at TEXT
        )"""
    )
    connection.close()

    store = StateStore(str(path))
    columns = {
        row["name"]
        for row in store.conn().execute("PRAGMA table_info(events)")
    }
    assert "checkpoint_json" in columns
