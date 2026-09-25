import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from orchestrator.state_store import StateStore


def workers(tmp_path):
    path = tmp_path / "state.db"
    first, second = StateStore(str(path)), StateStore(str(path))
    first.enqueue("delivery-a", "pull_request", {})
    second.enqueue("delivery-b", "pull_request", {})
    return path, (first, second), (first.claim_next(), second.claim_next())


def test_duplicate_deliveries_have_only_one_logical_owner(tmp_path):
    _, stores, events = workers(tmp_path)
    barrier = Barrier(2)

    def acquire(i):
        barrier.wait()
        return stores[i].claim_operation("repo/78/sha/qa",
            events[i]["delivery_id"], events[i]["lease_id"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(acquire, range(2)))
    assert sorted(results) == [False, True]
    winner = results.index(True)
    stores[winner].assert_operation("repo/78/sha/qa",
        events[winner]["delivery_id"], events[winner]["lease_id"])
    assert stores[winner].claim_operation("repo/78/sha/qa",
        events[winner]["delivery_id"], events[winner]["lease_id"])


def test_expiry_allows_reclaim_and_fences_old_worker(tmp_path):
    path, (first, second), (a, b) = workers(tmp_path)
    assert first.claim_operation("same-operation", a["delivery_id"], a["lease_id"])
    assert not second.claim_operation("same-operation", b["delivery_id"], b["lease_id"])
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE events SET lease_expires_at=? WHERE delivery_id=?",
                           ("2000-01-01T00:00:00+00:00", a["delivery_id"]))
    assert second.claim_operation("same-operation", b["delivery_id"], b["lease_id"])
    with pytest.raises(RuntimeError, match="WORKER_OPERATION_LEASE_LOST"):
        first.assert_operation("same-operation", a["delivery_id"], a["lease_id"])
    with pytest.raises(RuntimeError, match="WORKER_LEASE_LOST"):
        first.claim_operation("same-operation", a["delivery_id"], a["lease_id"])
    assert not first.heartbeat(a["delivery_id"], a["lease_id"])


def test_terminal_event_releases_claim_but_other_phases_are_independent(tmp_path):
    _, (first, second), (a, b) = workers(tmp_path)
    assert first.claim_operation("repo/78/sha/qa", a["delivery_id"], a["lease_id"])
    assert second.claim_operation("repo/78/sha/review", b["delivery_id"], b["lease_id"])
    assert first.finish(a["delivery_id"], "done", lease_id=a["lease_id"])
    assert second.claim_operation("repo/78/sha/qa", b["delivery_id"], b["lease_id"])
