import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from orchestrator.queue_discovery import candidate, scan_once, discovery_loop
from orchestrator.github_client import GitHubClient
from orchestrator.state_store import StateStore


def pr(phase='qa', number=78):
    return dict(number=number, state='open', draft=False,
        body='<!-- agent-task-id:GH-ISSUE-77 -->', base={'ref': 'main'},
        head={'ref': 'feature', 'sha': 'a' * 40,
              'repo': {'full_name': 'owner/repo', 'default_branch': 'main'}},
        labels=['agent:workbuddy' if phase in {'prototype', 'qa'} else 'agent:workreview',
                'phase:' + phase, 'status:todo'])


@pytest.mark.parametrize('change', ['human', 'conflict', 'blocker', 'fork', 'main', 'task', 'draft', 'closed', 'deploy'])
def test_discovery_rejects_unsafe_or_ambiguous_work(change):
    value = pr()
    if change == 'human': value['labels'] += ['approval:production-required']
    elif change == 'conflict': value['labels'] += ['status:running']
    elif change == 'blocker': value['labels'] += ['recovery:qa-evidence']
    elif change == 'fork': value['head']['repo']['full_name'] = 'other/repo'
    elif change == 'main': value['head']['ref'] = 'main'
    elif change == 'task': value['body'] += '<!-- agent-task-id:another -->'
    elif change == 'draft': value['draft'] = True
    elif change == 'closed': value['state'] = 'closed'
    else: value['labels'][1] = 'phase:deploy'
    assert candidate(value, 'owner/repo') is None


def test_missed_webhook_discovered_once_and_account_phase_not_executed(tmp_path):
    store = StateStore(str(tmp_path / 'state.db'))
    values = [pr(), pr('code-review', 79)]
    async def snapshots(*args): return copy.deepcopy(values)
    github = SimpleNamespace(list_open_prs=snapshots)
    assert candidate(values[1], 'owner/repo')['phase'] == 'phase:code-review'
    assert asyncio.run(scan_once(store, github, 'owner/repo')) == 1
    assert asyncio.run(scan_once(store, github, 'owner/repo')) == 0
    event = store.claim_next()
    assert event['payload']['number'] == 78
    assert event['payload']['label']['name'] == 'status:todo'
    assert store.claim_next() is None
    values[0]['head']['sha'] = 'b' * 40
    assert asyncio.run(scan_once(store, github, 'owner/repo')) == 1


def test_all_pages_are_read():
    github = GitHubClient('test-only')
    pages = []
    async def request(method, url, **kwargs):
        pages.append(kwargs['params']['page'])
        return httpx.Response(200, json=[pr(number=i) for i in range(100)] if len(pages) == 1 else [pr(number=101)])
    github._request = request
    assert len(asyncio.run(github.list_open_prs('owner/repo'))) == 101
    assert pages == [1, 2]


def test_transient_scan_error_does_not_kill_discovery(tmp_path):
    store = StateStore(str(tmp_path / 'state.db'))
    async def run():
        stop = asyncio.Event()
        calls = 0
        async def snapshots(*args):
            nonlocal calls
            calls += 1
            if calls == 1: raise RuntimeError('temporary')
            stop.set()
            return [pr()]
        await discovery_loop(stop, store, SimpleNamespace(list_open_prs=snapshots), 'owner/repo', .001)
    asyncio.run(run())
    assert store.claim_next()['payload']['number'] == 78
