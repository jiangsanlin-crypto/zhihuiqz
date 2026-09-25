from __future__ import annotations

import sqlite3

from orchestrator.state_store import StateStore


def test_existing_database_migrates_and_retries_with_report_checkpoint(tmp_path):
    path = tmp_path / "state.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE events (delivery_id TEXT PRIMARY KEY, "
            "event_name TEXT, payload_json TEXT, status TEXT DEFAULT 'queued', "
            "attempts INTEGER DEFAULT 0, error TEXT, created_at TEXT, "
            "updated_at TEXT)"
        )

    store = StateStore(str(path))
    assert store.enqueue("delivery-1", "pull_request", {"number": 78})
    assert store.claim_next()["attempts"] == 1
    checkpoint = {
        "source_sha": "reviewed-sha",
        "result": {"status": "success", "changes": [
            {"path": "reports/qa.md", "content": "pass"}
        ]},
    }
    store.checkpoint("delivery-1", checkpoint)

    # A live lease must survive process startup; expire it to model a crash.
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE events SET lease_expires_at=? WHERE delivery_id=?",
            ("2000-01-01T00:00:00+00:00", "delivery-1"),
        )
    restarted = StateStore(str(path))
    resumed = restarted.claim_next()
    assert resumed["attempts"] == 2
    assert resumed["checkpoint"] == checkpoint
    assert resumed["payload"] == {"number": 78}
