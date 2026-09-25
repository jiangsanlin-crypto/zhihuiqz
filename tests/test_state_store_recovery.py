from orchestrator.state_store import StateStore


def test_restart_recovers_running_event_to_retry(tmp_path):
    db = tmp_path / "orchestrator.db"
    first = StateStore(str(db))
    assert first.enqueue("delivery-1", "pull_request", {"number": 7})

    claimed = first.claim_next()
    assert claimed is not None
    assert claimed["delivery_id"] == "delivery-1"
    assert claimed["attempts"] == 1
    assert first.get("delivery-1")["status"] == "running"

    restarted = StateStore(str(db))
    recovered = restarted.get("delivery-1")
    assert recovered["status"] == "retry"
    assert recovered["attempts"] == 1
    assert "recovered after orchestrator restart" in recovered["error"]

    claimed_again = restarted.claim_next()
    assert claimed_again is not None
    assert claimed_again["delivery_id"] == "delivery-1"
    assert claimed_again["attempts"] == 2


def test_completed_event_is_not_requeued_on_restart(tmp_path):
    db = tmp_path / "orchestrator.db"
    first = StateStore(str(db))
    first.enqueue("delivery-2", "pull_request", {"number": 8})
    first.claim_next()
    first.finish("delivery-2", "done")

    restarted = StateStore(str(db))
    assert restarted.get("delivery-2")["status"] == "done"
    assert restarted.claim_next() is None


def test_failed_event_is_not_requeued_on_restart(tmp_path):
    db = tmp_path / "orchestrator.db"
    first = StateStore(str(db))
    first.enqueue("delivery-3", "pull_request", {"number": 9})
    first.claim_next()
    first.finish("delivery-3", "failed", "retry budget exhausted")

    restarted = StateStore(str(db))
    assert restarted.get("delivery-3")["status"] == "failed"
    assert restarted.claim_next() is None
