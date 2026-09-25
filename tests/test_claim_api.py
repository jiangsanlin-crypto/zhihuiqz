import copy
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.claim_api import create_claim_router
from orchestrator.state_store import StateStore

SHA = "a" * 40
AUTH = {"Authorization": "Bearer test-only-token"}


def payload(**kwargs):
    return dict(repository="owner/repo", pr_number=78, source_sha=SHA,
                head_ref="feature", task_id="GH-ISSUE-77", phase="phase:code-review",
                worker_id="account-worker", request_id="request-1", **kwargs)


@pytest.fixture
def setup(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    pr = {"state": "open", "head": {"sha": SHA, "ref": "feature",
          "repo": {"full_name": "owner/repo", "default_branch": "main"}},
          "base": {"ref": "main"}, "body": "<!-- agent-task-id:GH-ISSUE-77 -->",
          "labels": ["agent:workreview", "phase:code-review", "status:todo"]}

    async def snapshot(*args):
        return copy.deepcopy(pr)

    github = SimpleNamespace(get_pr_snapshot=snapshot)
    settings = SimpleNamespace(orchestrator_token="test-only-token", github_repository="owner/repo")
    app = FastAPI()
    app.include_router(create_claim_router(store, github, settings))
    return TestClient(app), store, pr, github


def owned(claim, worker="account-worker"):
    return {"delivery_id": claim["delivery_id"], "lease_id": claim["lease_id"], "worker_id": worker}


def test_authentication_idempotency_heartbeat_and_release(setup):
    client, store, pr, _ = setup
    assert client.post("/claims/acquire", json=payload()).status_code == 401
    first = client.post("/claims/acquire", json=payload(), headers=AUTH)
    assert first.status_code == 200
    claim = first.json()
    pr["labels"][-1] = "status:running"
    assert client.post("/claims/acquire", json=payload(), headers=AUTH).json() == claim
    assert client.post("/claims/heartbeat", json=owned(claim), headers=AUTH).status_code == 200
    assert client.post("/claims/release", json=owned(claim, "other"), headers=AUTH).status_code == 409
    assert client.post("/claims/release", json=owned(claim), headers=AUTH).status_code == 200
    assert client.post("/claims/heartbeat", json=owned(claim), headers=AUTH).status_code == 409
    assert pr["labels"][-1] == "status:running"  # Lease APIs never project labels.


@pytest.mark.parametrize("external_first", [True, False])
def test_external_workers_and_internal_events_share_one_lock(setup, external_first):
    client, store, _, _ = setup
    store.enqueue("internal", "pull_request", {})
    event = store.claim_next()
    key = '["owner/repo",78,"' + SHA + '","phase:code-review"]'
    if external_first:
        claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
        assert not store.claim_operation(key, event["delivery_id"], event["lease_id"])
        assert client.post("/claims/release", json=owned(claim), headers=AUTH).status_code == 200
        assert store.claim_operation(key, event["delivery_id"], event["lease_id"])
    else:
        assert store.claim_operation(key, event["delivery_id"], event["lease_id"])
        result = client.post("/claims/acquire", json=payload(), headers=AUTH)
        assert result.status_code == 409
        assert result.json()["detail"] == "ANOTHER_WORKER_OWNS_LEASE"


def test_expired_external_claim_is_reclaimable_but_never_queued_for_execution(setup):
    client, store, _, _ = setup
    old = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE events SET lease_expires_at=? WHERE delivery_id=?",
                           ("2000-01-01T00:00:00+00:00", old["delivery_id"]))
    assert store.recover_interrupted() == 0
    assert store.claim_next() is None
    assert client.post("/claims/heartbeat", json=owned(old), headers=AUTH).status_code == 409
    new = client.post("/claims/acquire", json=dict(payload(), request_id="request-2"), headers=AUTH)
    assert new.status_code == 200
    assert new.json()["lease_id"] != old["lease_id"]
    assert client.post("/claims/release", json=owned(old), headers=AUTH).status_code == 409


@pytest.mark.parametrize("change", ["head", "human_wait", "branch", "task", "conflicting_labels"])
def test_live_state_change_revokes_heartbeat_without_editing_github(setup, change):
    client, store, pr, _ = setup
    claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
    if change == "head":
        pr["head"]["sha"] = "b" * 40
    elif change == "human_wait":
        pr["labels"] = ["status:review", "approval:production-required"]
    elif change == "branch":
        pr["head"]["ref"] = "main"
    elif change == "task":
        pr["body"] = "<!-- agent-task-id:GH-ISSUE-99 -->"
    else:
        pr["labels"].append("status:running")
    before = copy.deepcopy(pr)
    assert client.post("/claims/heartbeat", json=owned(claim), headers=AUTH).status_code == 409
    assert store.get(claim["delivery_id"])["status"] == "superseded"
    assert pr == before


def test_push_during_claim_acquisition_cannot_return_a_live_lease(setup):
    client, store, pr, github = setup
    calls = 0

    async def snapshot(*args):
        nonlocal calls
        calls += 1
        result = copy.deepcopy(pr)
        if calls == 2:
            result["head"]["sha"] = "b" * 40
        return result

    github.get_pr_snapshot = snapshot
    result = client.post("/claims/acquire", json=payload(), headers=AUTH)
    assert result.status_code == 409
    delivery = store.external_delivery_id("account-worker", "request-1")
    assert store.get(delivery)["status"] == "superseded"
