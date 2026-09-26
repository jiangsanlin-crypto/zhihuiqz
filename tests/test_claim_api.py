import copy
import json
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


@pytest.fixture
def projection_setup(setup):
    client, store, pr, github = setup
    comments = [
        {"id": -1, "created_at": "2026-09-25T00:10:00Z", "user": {"login": "owner"},
         "body": "<!-- agent-handoff:v1 -->\n```json\n" + json.dumps({
             "task_id": "GH-ISSUE-77", "from_agent": "workbuddy", "to_agent": "chatgpt",
             "phase": "prototype_validation", "source_sha": SHA, "status": "success",
             "blockers": [], "checks": [{"name": "prototype_gate", "status": "passed"}],
             "pr_number": 78,
         }) + "\n```"},
        {"id": 0, "created_at": "2026-09-25T00:20:00Z", "user": {"login": "owner"},
         "body": "<!-- agent-handoff:v1 -->\n```json\n" + json.dumps({
             "task_id": "GH-ISSUE-77", "from_agent": "chatgpt", "to_agent": "workreview",
             "phase": "implementation", "source_sha": SHA, "status": "success",
             "blockers": [], "checks": [{"name": "implementation", "status": "passed"}],
             "pr_number": 78,
         }) + "\n```"},
        {"id": 1, "created_at": "2026-09-25T01:00:00Z", "user": {"login": "owner"},
         "body": "<!-- agent-claim:v1 -->\ntask_id=GH-ISSUE-77\n"
                 f"agent=workreview\nphase=code-review\nsource_sha={SHA}"},
        {"id": 2, "created_at": "2026-09-25T02:00:00Z", "user": {"login": "owner"},
         "body": "<!-- agent-handoff:v1 -->\n```json\n" + json.dumps({
             "task_id": "GH-ISSUE-77", "from_agent": "workreview", "to_agent": "workbuddy",
             "phase": "code_review", "source_sha": SHA, "status": "success", "blockers": [],
             "checks": [{"name": "independent_code_review", "status": "passed"}], "pr_number": 78,
         }) + "\n```"},
    ]
    runs = {"workflow_runs": [{"id": 10, "name": "CI", "path": ".github/workflows/ci.yml",
        "head_sha": SHA, "head_branch": "feature", "event": "pull_request",
        "status": "completed", "conclusion": "success"}]}
    writes = []

    async def list_comments(*args):
        return copy.deepcopy(comments)

    async def list_runs(*args):
        return copy.deepcopy(runs)

    async def set_labels(repo, number, values):
        writes.append(values)
        pr["labels"] = values

    github.list_comments, github.list_workflow_runs, github.set_labels = list_comments, list_runs, set_labels
    return client, store, pr, github, comments, runs, writes


def test_verified_advance_is_audited_and_retry_does_not_write_twice(projection_setup):
    client, store, pr, _, _, _, writes = projection_setup
    pr["labels"].append("keep:me")
    claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
    result = client.post("/claims/advance", json=owned(claim), headers=AUTH)
    assert result.status_code == 200
    assert result.json()["status"] == "applied"
    assert pr["labels"] == ["agent:workbuddy", "keep:me", "phase:qa", "status:todo"]
    assert store.get(claim["delivery_id"])["status"] == "done"
    assert len(result.json()["audit"]["evidence_generation"]) == 64
    again = client.post("/claims/advance", json=owned(claim), headers=AUTH)
    assert again.json()["status"] == "already_applied"
    assert len(writes) == 1
    with sqlite3.connect(store.path) as connection:
        audits = connection.execute("SELECT payload_json FROM recovery_audit WHERE delivery_id=?",
                                    (claim["delivery_id"],)).fetchall()
    decoded = [json.loads(x[0]) for x in audits]
    shared = [x for x in decoded if x['rule_id'] == 'SHARED_STATE_WRITER']
    phase = [x for x in decoded if x['rule_id'] != 'SHARED_STATE_WRITER']
    assert sorted(x['status'] for x in shared) == ['applied', 'planned']
    assert sorted(x['status'] for x in phase) == ['applied', 'planned']


def test_failed_ci_and_missing_independent_review_do_not_write(projection_setup):
    client, _, _, _, comments, runs, writes = projection_setup
    claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
    runs["workflow_runs"][0]["conclusion"] = "action_required"
    assert client.post("/claims/advance", json=owned(claim), headers=AUTH).status_code == 409
    runs["workflow_runs"][0]["conclusion"] = "success"
    claim_index = next(i for i,x in enumerate(comments) if "<!-- agent-claim:v1 -->" in x["body"])
    old_claim = comments.pop(claim_index)
    assert client.post("/claims/advance", json=owned(claim), headers=AUTH).status_code == 409
    assert writes == []
    comments.insert(claim_index, old_claim)
    assert client.post("/claims/advance", json=owned(claim), headers=AUTH).status_code == 200


def test_retry_recovers_labels_written_before_network_failure(projection_setup):
    client, store, pr, github, _, _, writes = projection_setup
    claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
    original = github.set_labels

    async def interrupted(*args):
        await original(*args)
        raise RuntimeError("simulated response loss")

    github.set_labels = interrupted
    with pytest.raises(RuntimeError, match="simulated response loss"):
        client.post("/claims/advance", json=owned(claim), headers=AUTH)
    assert "phase:qa" in pr["labels"]
    assert store.get(claim["delivery_id"])["status"] == "running"
    assert client.post("/claims/heartbeat", json=owned(claim), headers=AUTH).status_code == 200
    github.set_labels = original
    retry = client.post("/claims/advance", json=owned(claim), headers=AUTH)
    assert retry.status_code == 200
    assert len(writes) == 1


def test_human_wait_during_evidence_read_is_never_overwritten(projection_setup):
    client, _, pr, github, _, runs, writes = projection_setup
    claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()

    async def human_wait(*args):
        pr["labels"] = ["status:review", "approval:production-required"]
        return runs

    github.list_workflow_runs = human_wait
    result = client.post("/claims/advance", json=owned(claim), headers=AUTH)
    assert result.status_code == 409
    assert writes == []
    assert pr["labels"] == ["status:review", "approval:production-required"]


def test_qa_requires_terminal_policy_before_human_wait(projection_setup):
    client, store, pr, _, comments, _, writes = projection_setup
    pr["labels"] = ["agent:workbuddy", "phase:qa", "status:todo"]
    claim = client.post("/claims/acquire", json=dict(payload(), phase="phase:qa"), headers=AUTH).json()
    assert client.post("/claims/advance", json=owned(claim), headers=AUTH).status_code == 409
    comments.extend([
        {"user": {"login": "github-actions[bot]"}, "body": "<!-- terminal-policy:v1 -->\n"
         f"task_id=GH-ISSUE-77\nsource_sha={SHA}\npolicy=stop_after_qa\nrelease_enabled=false"},
        {"user": {"login": "github-actions[bot]"}, "body": "<!-- agent-handoff:v1 -->\n```json\n" + json.dumps({
            "task_id": "GH-ISSUE-77", "source_sha": SHA, "from_agent": "workbuddy",
            "phase": "qa_acceptance", "status": "success", "blockers": [],
        }) + "\n```"},
    ])
    assert client.post("/claims/advance", json=owned(claim), headers=AUTH).status_code == 200
    assert pr["labels"] == ["approval:production-required", "status:review"]
    assert store.get(claim["delivery_id"])["status"] == "done"
    assert len(writes) == 1


def test_callers_cannot_supply_arbitrary_target_labels(projection_setup):
    client, _, _, _, _, _, writes = projection_setup
    claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
    result = client.post("/claims/advance", json=dict(owned(claim), labels=["status:done"]), headers=AUTH)
    assert result.status_code == 422
    assert writes == []


def test_one_pr_projection_lock_serializes_different_phase_writers(projection_setup):
    client, store, _, _, _, _, writes = projection_setup
    claim = client.post("/claims/acquire", json=payload(), headers=AUTH).json()
    store.enqueue("other-stage", "pull_request", {})
    competitor = store.claim_next()
    key = json.dumps(["owner/repo", 78, "state-projection"])
    assert store.claim_operation(key, competitor["delivery_id"], competitor["lease_id"])
    result = client.post("/claims/advance", json=owned(claim), headers=AUTH)
    assert result.status_code == 409
    assert result.json()["detail"] == "ANOTHER_WORKER_OWNS_PROJECTION"
    assert writes == []


@pytest.mark.parametrize("phase,agent,target", [
    ("phase:implementation", "chatgpt", "phase:code-review"),
    ("phase:prototype", "workbuddy", "phase:implementation"),
    ("phase:escalation-repair", "workreview", "phase:code-review"),
])
def test_other_phase_transitions_do_not_skip_independent_review(projection_setup, phase, agent, target):
    client, _, pr, _, comments, _, _ = projection_setup
    pr["labels"] = [f"agent:{agent}", phase, "status:todo"]
    if phase == "phase:escalation-repair":
        body = ("<!-- agent-repair:v1 -->\ntask_id=GH-ISSUE-77\n"
                f"source_sha={SHA}\nagent=workreview\nphase=escalation-repair\nstatus=waiting_ci")
    else:
        body = "<!-- agent-handoff:v1 -->\n```json\n" + json.dumps({
            "task_id": "GH-ISSUE-77", "from_agent": agent,
            "to_agent": "workreview" if agent == "chatgpt" else "chatgpt",
            "phase": "implementation" if agent == "chatgpt" else "prototype_validation",
            "source_sha": SHA, "status": "success", "blockers": [], "pr_number": 78,
        }) + "\n```"
    comments[:] = [{"user": {"login": "owner"}, "body": body}]
    claim = client.post("/claims/acquire", json=dict(payload(), phase=phase), headers=AUTH).json()
    if phase == "phase:escalation-repair":
        comments.append({"user": {"login": "owner"}, "id": 2,
                         "body": body.replace("status=waiting_ci", "status=blocked")})
        assert client.post("/claims/advance", json=owned(claim), headers=AUTH).status_code == 409
        comments.pop()
    result = client.post("/claims/advance", json=owned(claim), headers=AUTH)
    assert result.status_code == 200
    assert target in pr["labels"]
    assert "phase:qa" not in pr["labels"]


def test_start_requires_ownership_and_keeps_lease_for_execution(projection_setup):
    client, store, pr, _, _, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim)).status_code == 401
    assert client.post('/claims/start', json=owned(claim, 'other'), headers=AUTH).status_code == 409
    pr['labels'].append('keep:me')
    result = client.post('/claims/start', json=owned(claim), headers=AUTH)
    assert result.status_code == 200
    assert pr['labels'] == ['agent:workreview', 'keep:me', 'phase:code-review', 'status:running']
    assert store.get(claim['delivery_id'])['lease_id'] == claim['lease_id']
    assert client.post('/claims/heartbeat', json=owned(claim), headers=AUTH).status_code == 200
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).json()['status'] == 'already_applied'
    assert len(writes) == 1
    assert client.post('/claims/advance', json=owned(claim), headers=AUTH).status_code == 200
    assert 'phase:qa' in pr['labels']


def test_start_recovers_response_loss_without_repeating_put(projection_setup):
    client, store, pr, github, _, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    original = github.set_labels
    async def lost(*args):
        await original(*args)
        raise RuntimeError('lost start response')
    github.set_labels = lost
    with pytest.raises(RuntimeError, match='lost start response'):
        client.post('/claims/start', json=owned(claim), headers=AUTH)
    github.set_labels = original
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200
    assert len(writes) == 1
    with sqlite3.connect(store.path) as connection:
        audits = connection.execute('SELECT payload_json FROM recovery_audit').fetchall()
    assert {json.loads(a[0])['status'] for a in audits} == {'planned', 'applied'}


@pytest.mark.parametrize('change', ['head', 'human_wait', 'expiry', 'label_drift'])
def test_start_fences_changes_before_label_write(projection_setup, change):
    client, store, pr, github, _, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    original = github.get_pr_snapshot
    reads = 0
    async def changed(*args):
        nonlocal reads
        reads += 1
        if reads == 2:
            if change == 'head':
                pr['head']['sha'] = 'b' * 40
            elif change == 'human_wait':
                pr['labels'] = ['status:review', 'approval:production-required']
            elif change == 'label_drift':
                pr['labels'].append('keep:new')
            else:
                with sqlite3.connect(store.path) as connection:
                    connection.execute('UPDATE events SET lease_expires_at=?', ('2000-01-01T00:00:00+00:00',))
        return await original(*args)
    github.get_pr_snapshot = changed
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 409
    assert writes == []


def test_start_qa_requires_live_independent_review_and_ci(projection_setup):
    client, _, pr, _, comments, runs, writes = projection_setup
    pr['labels'] = ['agent:workbuddy', 'phase:qa', 'status:todo']
    claim = client.post('/claims/acquire', json=dict(payload(), phase='phase:qa'), headers=AUTH).json()
    runs['workflow_runs'][0]['conclusion'] = 'failure'
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 409
    runs['workflow_runs'][0]['conclusion'] = 'success'
    claim_index = next(i for i,x in enumerate(comments) if "<!-- agent-claim:v1 -->" in x["body"])
    review_claim = comments.pop(claim_index)
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 409
    assert writes == []
    comments.insert(claim_index, review_claim)
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200


def test_start_replay_never_undoes_requeue(projection_setup):
    client, _, pr, _, _, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200
    pr['labels'] = ['agent:workreview', 'phase:code-review', 'status:todo']
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 409
    assert len(writes) == 1


def test_ready_endpoint_is_authenticated_read_only_and_excludes_human_wait(projection_setup):
    client, _, pr, github, _, _, writes = projection_setup
    pr['number'] = 78
    async def open_prs(*args): return [copy.deepcopy(pr)]
    github.list_open_prs = open_prs
    assert client.get('/claims/ready').status_code == 401
    assert client.get('/claims/ready', headers=AUTH).json()['candidates'][0]['pr_number'] == 78
    pr['labels'] = ['status:review', 'approval:production-required']
    assert client.get('/claims/ready', headers=AUTH).json() == {'candidates': []}
    assert writes == []


def test_account_consumer_end_to_end_with_real_claim_router(projection_setup):
    import asyncio
    import httpx
    from orchestrator.claim_client import ClaimClient
    client, store, pr, github, _, _, writes = projection_setup
    pr['number'] = 78
    async def open_prs(*args): return [copy.deepcopy(pr)]
    github.list_open_prs = open_prs

    async def run():
        transport = httpx.ASGITransport(app=client.app)
        worker = ClaimClient('https://claims.test', 'test-only-token', transport=transport)
        rival = ClaimClient('https://claims.test', 'test-only-token', transport=transport)
        async def review(binding):
            assert 'status:running' in pr['labels']
            with pytest.raises(httpx.HTTPStatusError) as error:
                await rival.acquire(binding, 'rival', 'rival-request', delays=(0,))
            assert error.value.response.status_code == 409
            return 'verified exact-SHA review'
        assert await worker.consume_one('phase:code-review', 'account-worker', review) == 'verified exact-SHA review'
        assert worker.ownership is None
        await worker.close()
        await rival.close()
    asyncio.run(run())
    assert pr['labels'] == ['agent:workbuddy', 'phase:qa', 'status:todo']
    assert len(writes) == 2  # READY -> RUNNING -> verified QA READY.
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT count(*) FROM events WHERE status='running'").fetchone()[0] == 0


def expire_claim(store, delivery):
    with sqlite3.connect(store.path) as connection:
        connection.execute('UPDATE events SET lease_expires_at=? WHERE delivery_id=?',
                           ('2000-01-01T00:00:00+00:00', delivery))


def test_external_expiry_without_result_requeues_and_fences_old_worker(projection_setup):
    import asyncio
    from orchestrator.external_recovery import recover_external_once
    client, store, pr, github, comments, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200
    comments.clear()
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 0
    expire_claim(store, claim['delivery_id'])
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 1
    assert 'status:todo' in pr['labels']
    assert client.post('/claims/heartbeat', json=owned(claim), headers=AUTH).status_code == 409
    assert client.post('/claims/acquire', json=payload(), headers=AUTH).status_code == 409
    replacement = client.post('/claims/acquire', json=dict(payload(), request_id='new'), headers=AUTH)
    assert replacement.status_code == 200
    assert len(writes) == 2
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 0


def test_external_expiry_uses_durable_pass_without_rerunning_worker(projection_setup):
    import asyncio
    from orchestrator.external_recovery import recover_external_once
    client, store, pr, github, _, runs, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    client.post('/claims/start', json=owned(claim), headers=AUTH)
    expire_claim(store, claim['delivery_id'])
    runs['workflow_runs'][0]['conclusion'] = 'action_required'
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 0
    assert 'status:running' in pr['labels']  # Result exists: no duplicate execution.
    assert client.post('/claims/acquire', json=payload(), headers=AUTH).status_code == 409
    runs['workflow_runs'][0]['conclusion'] = 'success'
    expire_claim(store, claim['delivery_id'])
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 1
    assert pr['labels'] == ['agent:workbuddy', 'phase:qa', 'status:todo']
    assert len(writes) == 2


@pytest.mark.parametrize('change', ['head', 'human', 'untracked_running'])
def test_external_recovery_does_not_guess_ownership_or_override_new_state(projection_setup, change):
    import asyncio
    from orchestrator.external_recovery import recover_external_once
    client, store, pr, github, _, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    if change == 'head': pr['head']['sha'] = 'b' * 40
    elif change == 'human': pr['labels'] = ['status:review', 'approval:production-required']
    else: pr['labels'][-1] = 'status:running'
    before = copy.deepcopy(pr)
    expire_claim(store, claim['delivery_id'])
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 0
    assert pr == before
    assert writes == []


def test_external_recovery_label_response_loss_is_replay_safe(projection_setup):
    import asyncio
    from orchestrator.external_recovery import recover_external_once
    client, store, pr, github, comments, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    client.post('/claims/start', json=owned(claim), headers=AUTH)
    comments.clear()
    expire_claim(store, claim['delivery_id'])
    original = github.set_labels
    async def lost(*args):
        await original(*args)
        raise RuntimeError('response lost')
    github.set_labels = lost
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 0
    assert 'status:todo' in pr['labels']
    assert store.get(claim['delivery_id'])['status'] == 'running'
    github.set_labels = original
    expire_claim(store, claim['delivery_id'])
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 1
    assert len(writes) == 2


def test_external_recovery_cas_only_one_reconciler_can_take_lease(projection_setup):
    client, store, _, _, _, _, _ = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    expire_claim(store, claim['delivery_id'])
    assert store.reclaim_external(claim['delivery_id'], claim['lease_id']) is not None
    assert store.reclaim_external(claim['delivery_id'], claim['lease_id']) is None
    assert client.post('/claims/acquire', json=payload(), headers=AUTH).status_code == 409


def test_external_durable_failure_never_requeues_or_advances(projection_setup):
    import asyncio
    from orchestrator.external_recovery import recover_external_once
    client, store, pr, github, comments, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    client.post('/claims/start', json=owned(claim), headers=AUTH)
    comments[-1]['body'] = comments[-1]['body'].replace('"status": "success"', '"status": "failed"')
    expire_claim(store, claim['delivery_id'])
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 0
    assert len(writes) == 1
    assert 'status:running' in pr['labels']
    with sqlite3.connect(store.path) as connection:
        audits = [json.loads(x[0]) for x in connection.execute('SELECT payload_json FROM recovery_audit')]
    assert any(a['status'] == 'waiting_evidence' for a in audits)


def test_new_human_wait_during_external_recovery_is_preserved(projection_setup):
    import asyncio
    from orchestrator.external_recovery import recover_external_once
    client, store, pr, github, _, runs, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    client.post('/claims/start', json=owned(claim), headers=AUTH)
    expire_claim(store, claim['delivery_id'])
    async def runs_with_human_wait(*args):
        pr['labels'] = ['status:review', 'approval:production-required']
        return runs
    github.list_workflow_runs = runs_with_human_wait
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 0
    assert len(writes) == 1
    assert pr['labels'] == ['status:review', 'approval:production-required']


def test_worker_decision_escalates_review_to_repair(projection_setup):
    client, store, pr, _, _, _, writes = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200
    result = client.post('/claims/decision', json=dict(
        owned(claim), decision='repair', reason_code='REVIEW_DEFECT'
    ), headers=AUTH)
    assert result.status_code == 200
    assert pr['labels'] == ['agent:workreview', 'phase:escalation-repair', 'status:todo']
    assert store.get(claim['delivery_id'])['status'] == 'done'
    assert len(writes) == 2


def test_worker_decision_escalates_exhausted_implementation(projection_setup):
    client, store, pr, _, _, _, writes = projection_setup
    pr['labels'] = ['agent:chatgpt', 'phase:implementation', 'status:todo']
    claim = client.post('/claims/acquire', json=dict(
        payload(), phase='phase:implementation'
    ), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200
    result = client.post('/claims/decision', json=dict(
        owned(claim), decision='repair', reason_code='IMPLEMENTATION_RETRY_EXHAUSTED'
    ), headers=AUTH)
    assert result.status_code == 200
    assert pr['labels'] == ['agent:workreview', 'phase:escalation-repair', 'status:todo']
    assert store.get(claim['delivery_id'])['status'] == 'done'
    assert len(writes) == 2


def test_worker_decision_retry_and_block_are_controller_projected(projection_setup):
    client, store, pr, _, _, _, _ = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200
    retry = client.post('/claims/decision', json=dict(
        owned(claim), decision='retry', reason_code='TRANSIENT_TOOL'
    ), headers=AUTH)
    assert retry.status_code == 200
    assert pr['labels'] == ['agent:workreview', 'phase:code-review', 'status:todo']

    claim2 = client.post('/claims/acquire', json=dict(
        payload(), request_id='request-block'
    ), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim2), headers=AUTH).status_code == 200
    blocked = client.post('/claims/decision', json=dict(
        owned(claim2), decision='block', reason_code='HUMAN_POLICY'
    ), headers=AUTH)
    assert blocked.status_code == 200
    assert set(pr['labels']) == {
        'agent:workreview', 'phase:code-review', 'status:blocked', 'blocker:human-policy'
    }
    assert store.get(claim2['delivery_id'])['status'] == 'done'


@pytest.fixture
def publication_setup(projection_setup):
    client, store, pr, github, comments, runs, writes = projection_setup
    pr['labels'] = ['agent:chatgpt', 'phase:implementation', 'status:todo']
    async def commit(*args):
        return {'sha': 'b' * 40, 'parents': [{'sha': SHA}], 'files': [{'filename': 'app.py'}]}
    github.get_publication_commit = commit
    claim = client.post('/claims/acquire', json=dict(payload(), phase='phase:implementation'), headers=AUTH).json()
    assert client.post('/claims/start', json=owned(claim), headers=AUTH).status_code == 200
    return projection_setup, claim


def test_declared_head_transfer_requires_new_sha_evidence(publication_setup):
    (client, store, pr, _, comments, runs, writes), claim = publication_setup
    assert client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH).status_code == 200
    assert client.post('/claims/confirm-head', json=owned(claim), headers=AUTH).status_code == 409
    pr['head']['sha'] = 'b'*40
    result = client.post('/claims/confirm-head', json=owned(claim), headers=AUTH)
    assert result.status_code == 200
    assert result.json()['source_sha'] == 'b'*40
    assert client.post('/claims/confirm-head', json=owned(claim), headers=AUTH).status_code == 200
    assert client.post('/claims/heartbeat', json=owned(claim), headers=AUTH).json()['source_sha'] == 'b'*40
    assert client.post('/claims/advance', json=owned(claim), headers=AUTH).status_code == 409
    assert len(writes) == 1
    comments[:] = [{'user': {'login': 'owner'}, 'body': '<!-- agent-handoff:v1 -->\n```json\n' + json.dumps({
        'task_id': 'GH-ISSUE-77', 'from_agent': 'chatgpt', 'to_agent': 'workreview',
        'phase': 'implementation', 'status': 'success', 'blockers': [], 'source_sha': 'b'*40,
        'pr_number': 78}) + '\n```'}]
    runs['workflow_runs'][0]['head_sha'] = 'b'*40
    assert client.post('/claims/advance', json=owned(claim), headers=AUTH).status_code == 200
    assert pr['labels'] == ['agent:workreview', 'phase:code-review', 'status:todo']


@pytest.mark.parametrize('invalid', ['parent', 'merge', 'workflow', 'rename'])
def test_publication_rejects_unrelated_or_workflow_commits(publication_setup, invalid):
    (client, _, _, github, _, _, _), claim = publication_setup
    async def commit(*args):
        parents = [{'sha': SHA}]
        files = [{'filename': 'app.py'}]
        if invalid == 'parent': parents = [{'sha': 'c'*40}]
        elif invalid == 'merge': parents.append({'sha': 'c'*40})
        elif invalid == 'workflow': files = [{'filename': '.github/workflows/ci.yml'}]
        else: files = [{'filename': 'old.yml', 'previous_filename': '.github/workflows/ci.yml'}]
        return {'sha': 'b'*40, 'parents': parents, 'files': files}
    github.get_publication_commit = commit
    assert client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH).status_code == 409


@pytest.mark.parametrize('change', ['head', 'base', 'human'])
def test_confirmation_never_adopts_concurrent_changes(publication_setup, change):
    (client, store, pr, _, _, _, writes), claim = publication_setup
    client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH)
    pr['head']['sha'] = 'b'*40
    if change == 'head': pr['head']['sha'] = 'c'*40
    elif change == 'base': pr['base']['ref'] = 'another-base'
    else: pr['labels'] = ['status:review', 'approval:production-required']
    assert client.post('/claims/confirm-head', json=owned(claim), headers=AUTH).status_code == 409
    assert json.loads(store.get(claim['delivery_id'])['payload_json'])['source_sha'] == SHA
    assert len(writes) == 1


def test_worker_crash_after_declared_push_recovers_new_sha(publication_setup):
    import asyncio
    from orchestrator.external_recovery import recover_external_once
    (client, store, pr, github, comments, _, writes), claim = publication_setup
    client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH)
    pr['head']['sha'] = 'b'*40
    comments.clear()
    expire_claim(store, claim['delivery_id'])
    assert asyncio.run(recover_external_once(store, github, 'owner/repo')) == 1
    binding = json.loads(store.get(claim['delivery_id'])['payload_json'])
    assert binding['source_sha'] == 'b'*40
    assert pr['labels'] == ['agent:chatgpt', 'phase:implementation', 'status:todo']
    assert client.post('/claims/heartbeat', json=owned(claim), headers=AUTH).status_code == 409
    assert len(writes) == 2


def test_heartbeat_recovers_lost_confirmation(publication_setup):
    (client, _, pr, _, _, _, _), claim = publication_setup
    client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH)
    pr['head']['sha'] = 'b'*40
    assert client.post('/claims/heartbeat', json=owned(claim), headers=AUTH).json()['source_sha'] == 'b'*40


def test_review_phase_cannot_publish_code_using_its_review_lease(projection_setup):
    client, _, _, _, _, _, _ = projection_setup
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    client.post('/claims/start', json=owned(claim), headers=AUTH)
    response = client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH)
    assert response.status_code == 409
    assert response.json()['detail'] == 'PHASE_CANNOT_PUBLISH_CODE'


def test_base_retarget_and_ambiguous_task_revoke_claim(projection_setup):
    client, _, pr, _, _, _, _ = projection_setup
    pr['body'] += '\n<!-- agent-task-id:other-task -->'
    assert client.post('/claims/acquire', json=payload(), headers=AUTH).status_code == 409
    pr['body'] = '<!-- agent-task-id:GH-ISSUE-77 -->'
    claim = client.post('/claims/acquire', json=payload(), headers=AUTH).json()
    pr['base']['ref'] = 'other-base'
    assert client.post('/claims/heartbeat', json=owned(claim), headers=AUTH).status_code == 409


def test_publication_cannot_steal_new_sha_operation(publication_setup):
    (client, store, pr, _, _, _, _), claim = publication_setup
    client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH)
    store.enqueue('competitor', 'pull_request', {})
    rival = store.claim_next()
    key = json.dumps(['owner/repo', 78, 'b'*40, 'phase:implementation'], separators=(',', ':'))
    assert store.claim_operation(key, rival['delivery_id'], rival['lease_id'])
    pr['head']['sha'] = 'b'*40
    assert client.post('/claims/confirm-head', json=owned(claim), headers=AUTH).status_code == 409
    assert json.loads(store.get(claim['delivery_id'])['payload_json'])['source_sha'] == SHA


def test_atomic_move_handles_duplicate_confirmation_snapshot(publication_setup):
    (client, store, pr, _, _, _, _), claim = publication_setup
    client.post('/claims/prepare-head', json=dict(owned(claim), target_sha='b'*40), headers=AUTH)
    old_checkpoint = json.loads(store.get(claim['delivery_id'])['checkpoint_json'])
    pr['head']['sha'] = 'b'*40
    assert client.post('/claims/confirm-head', json=owned(claim), headers=AUTH).status_code == 200
    row = store.move_external_head(claim['delivery_id'], claim['lease_id'], SHA, 'b'*40, old_checkpoint)
    assert json.loads(row['payload_json'])['source_sha'] == 'b'*40
    assert json.loads(row['checkpoint_json'])['head_publication']['status'] == 'applied'


def test_account_consumer_publishes_and_hands_off_new_sha(projection_setup):
    import asyncio
    import httpx
    from orchestrator.claim_client import ClaimClient
    client, _, pr, github, comments, runs, _ = projection_setup
    pr['number'] = 78
    pr['labels'] = ['agent:chatgpt', 'phase:implementation', 'status:todo']
    async def prs(*args): return [copy.deepcopy(pr)]
    async def commit(*args): return {'sha': 'b'*40, 'parents': [{'sha': SHA}], 'files': [{'filename': 'app.py'}]}
    github.list_open_prs, github.get_publication_commit = prs, commit
    async def run():
        worker = ClaimClient('https://claims.test', 'test-only-token', transport=httpx.ASGITransport(app=client.app))
        async def implementation(binding):
            async def publish(): pr['head']['sha'] = 'b'*40
            assert await worker.publish_head('b'*40, publish) == 'b'*40
            assert binding['source_sha'] == 'b'*40
            runs['workflow_runs'][0]['head_sha'] = 'b'*40
            comments[:] = [{'user': {'login': 'owner'}, 'body': '<!-- agent-handoff:v1 -->\n```json\n' + json.dumps({
                'task_id': 'GH-ISSUE-77', 'from_agent': 'chatgpt', 'to_agent': 'workreview',
                'phase': 'implementation', 'status': 'success', 'blockers': [], 'source_sha': 'b'*40,
                'pr_number': 78}) + '\n```'}]
            return 'implemented'
        assert await worker.consume_one('phase:implementation', 'worker', implementation) == 'implemented'
        await worker.close()
    asyncio.run(run())
    assert pr['labels'] == ['agent:workreview', 'phase:code-review', 'status:todo']
