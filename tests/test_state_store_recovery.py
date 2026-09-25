import sqlite3

import pytest

from orchestrator.state_store import StateStore


def test_live_lease_cannot_be_stolen_on_second_worker_start(tmp_path):
    path = tmp_path / "orchestrator.db"
    first = StateStore(str(path))
    assert first.enqueue("delivery-1", "pull_request", {"number": 7})
    claimed = first.claim_next()
    second = StateStore(str(path))

    assert second.recover_interrupted() == 0
    assert second.claim_next() is None
    assert first.heartbeat("delivery-1", claimed["lease_id"])
    assert second.claim_next() is None
    first.checkpoint("delivery-1", {"step": "written"}, claimed["lease_id"])
    assert first.finish("delivery-1", "done", lease_id=claimed["lease_id"])
    assert second.claim_next() is None


def test_expired_lease_reclaimed_and_old_worker_fenced(tmp_path):
    path = tmp_path / "orchestrator.db"
    first = StateStore(str(path))
    first.enqueue("delivery-1", "pull_request", {"number": 7})
    old = first.claim_next()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE events SET lease_expires_at=? WHERE delivery_id=?",
            ("2000-01-01T00:00:00+00:00", "delivery-1"),
        )

    second = StateStore(str(path))
    new = second.claim_next()
    assert new["attempts"] == 2
    assert new["lease_id"] != old["lease_id"]
    assert not first.heartbeat("delivery-1", old["lease_id"])
    with pytest.raises(RuntimeError, match="WORKER_LEASE_LOST"):
        first.checkpoint("delivery-1", {"step": "stale"}, old["lease_id"])
    assert not first.finish("delivery-1", "done", lease_id=old["lease_id"])
    second.assert_lease("delivery-1", new["lease_id"])
    assert second.finish("delivery-1", "done", lease_id=new["lease_id"])


def test_completed_and_failed_events_do_not_requeue_on_restart(tmp_path):
    path = tmp_path / "orchestrator.db"
    first = StateStore(str(path))
    for number, status in ((2, "done"), (3, "failed")):
        delivery = f"delivery-{number}"
        first.enqueue(delivery, "pull_request", {"number": number})
        claim = first.claim_next()
        assert first.finish(delivery, status, lease_id=claim["lease_id"])

    restarted = StateStore(str(path))
    assert restarted.claim_next() is None
