import asyncio
import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest

from orchestrator import main
from orchestrator.models import AgentRunResult
from orchestrator.state_store import StateStore


def expire(store):
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE events SET lease_expires_at='2000-01-01T00:00:00+00:00'")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    store = StateStore(str(tmp_path / 'state.db'))
    pr = dict(number=78, state='open', body='<!-- agent-task-id:GH-ISSUE-77 -->',
        head={'sha': 'a'*40, 'ref': 'feature', 'repo': {'full_name': 'owner/repo'}},
        base={'ref': 'main'}, labels=['agent:workbuddy', 'phase:prototype', 'status:todo'])
    req = SimpleNamespace(task_id='GH-ISSUE-77', agent='workbuddy', repository='owner/repo',
        source_kind='pull_request', source_number=78, phase='phase:prototype',
        source_sha='a'*40, source_ref='feature')
    async def snapshot(*args): return copy.deepcopy(pr)
    async def labels(*args): return list(pr['labels'])
    async def comments(*args): return []
    async def set_labels(repo, number, labels): pr['labels'] = labels
    async def comment(*args): raise RuntimeError('comment response lost')
    github = SimpleNamespace(configured=True, get_pr_snapshot=snapshot,
        get_issue_labels=labels, list_comments=comments, set_labels=set_labels, comment=comment)
    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'github', github)
    monkeypatch.setattr(main, 'build', lambda *args: (copy.deepcopy(req), []))
    monkeypatch.setattr(main, 'validate_handoff', lambda *args, **kwargs: {})
    store.enqueue('task', 'pull_request', {})
    return store, pr, github


@pytest.mark.parametrize('write_applied', [False, True])
def test_worker_recovers_start_intent_on_either_side_of_label_put(setup, monkeypatch, write_applied):
    store, pr, github = setup
    calls = []
    original = github.set_labels
    async def interrupted(*args):
        if write_applied: await original(*args)
        raise RuntimeError('start response lost')
    async def run(req):
        calls.append(req.source_sha)
        raise RuntimeError('adapter reached')
    github.set_labels = interrupted
    monkeypatch.setattr(main, 'workbuddy', SimpleNamespace(run=run))
    with pytest.raises(RuntimeError, match='start response lost'):
        asyncio.run(main.process(store.claim_next()))
    assert json.loads(store.get('task')['checkpoint_json'])['stage'] == 'starting'
    assert calls == []
    expire(store)
    github.set_labels = original
    with pytest.raises(RuntimeError, match='adapter reached'):
        asyncio.run(main.process(store.claim_next()))
    assert calls == ['a'*40]
    assert 'status:running' in pr['labels']


def test_durable_failure_result_is_not_reexecuted_after_comment_failure(setup, monkeypatch):
    store, _, _ = setup
    calls = []
    async def run(req):
        calls.append(True)
        return AgentRunResult(status='blocked', summary='task needs clarification')
    monkeypatch.setattr(main, 'workbuddy', SimpleNamespace(run=run))
    for _ in range(2):
        with pytest.raises(RuntimeError, match='comment response lost'):
            asyncio.run(main.process(store.claim_next()))
        expire(store)
    assert calls == [True]


def test_human_wait_after_start_crash_is_not_resumed(setup, monkeypatch):
    store, pr, github = setup
    async def interrupted(*args): raise RuntimeError('network')
    github.set_labels = interrupted
    with pytest.raises(RuntimeError, match='network'):
        asyncio.run(main.process(store.claim_next()))
    expire(store)
    pr['labels'] = ['status:review', 'approval:production-required']
    with pytest.raises(RuntimeError, match='CHECKPOINT_WORKFLOW_STATE_SUPERSEDED'):
        asyncio.run(main.process(store.claim_next()))
    assert pr['labels'] == ['status:review', 'approval:production-required']
