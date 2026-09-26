import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.issue_intake import scan_issues, generation, create_intake_router
from orchestrator.state_store import StateStore

REPO = 'owner/repo'
AUTH = {'Authorization': 'Bearer test-only'}

@pytest.fixture
def intake(tmp_path):
    store = StateStore(str(tmp_path / 'intake.db'))
    issues = [dict(number=80, title='Repair queue', body='Implement discovery', state='open', labels=[], user={'login':'owner'})]
    prs = []
    async def get_issues(*args): return copy.deepcopy(issues)
    async def get_prs(*args): return copy.deepcopy(prs)
    github = SimpleNamespace(list_open_issues=get_issues, list_open_prs=get_prs)
    app = FastAPI()
    app.include_router(create_intake_router(store, github, SimpleNamespace(github_repository=REPO, orchestrator_token='test-only')))
    return store, issues, prs, github, TestClient(app)

def scan(data):
    return asyncio.run(scan_issues(data[0], data[3], REPO))

def claim(data, **extra):
    return dict(issue_number=80, generation=generation(data[1][0]), worker_id='planner', lease_id='attempt-token-0001', **extra)

def test_unlabelled_discovery_replay_and_authenticated_claim(intake):
    store, _, _, _, client = intake
    scan(intake)
    value = claim(intake)
    assert client.get('/intake/issues').status_code == 401
    assert client.post('/intake/acquire', json=value, headers=AUTH).status_code == 200
    scan(intake)
    assert client.post('/intake/acquire', json=value, headers=AUTH).status_code == 200
    row = client.get('/intake/issues', headers=AUTH).json()['issues'][0]
    assert row['status'] == 'leased' and not row['claimable']
    assert 'lease_id' not in row and 'worker_id' not in row
    assert len(store.intake_items(REPO)) == 1

def test_two_database_clients_cannot_both_claim(intake):
    store, _, _, _, _ = intake
    scan(intake)
    other = StateStore(store.path)
    def acquire(pair):
        db, worker = pair
        try:
            db.claim_issue(REPO,80,claim(intake)['generation'],worker,'token-for-'+worker)
            return True
        except RuntimeError:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(acquire, [(store,'one'), (other,'two')])) == [False,True]

@pytest.mark.parametrize('change', ['body','labels','closed','associated'])
def test_fresh_scan_revokes_stale_planner(intake, change):
    _, issues, prs, _, client = intake
    value = claim(intake)
    assert client.post('/intake/acquire',json=value,headers=AUTH).status_code == 200
    if change == 'body': issues[0]['body'] += ' changed'
    elif change == 'labels': issues[0]['labels'] = ['approval:owner']
    elif change == 'closed': issues.clear()
    else: prs.append({'number':83,'body':'Closes #80'})
    assert client.post('/intake/heartbeat',json=value,headers=AUTH).status_code == 409

@pytest.mark.parametrize('body,status', [('Closes #80','linked'),('<!-- agent-task-id:GH-ISSUE-80 -->','linked'),('Fixes owner/repo#80','linked'),('Resolves https://github.com/owner/repo/issues/80','linked'),('Related to #80','needs_link_resolution'),('Closes #80\nFixes #81','needs_link_resolution')])
def test_associations_prevent_duplicate_planning(intake,body,status):
    intake[2].append({'number':83,'body':body})
    scan(intake)
    assert intake[0].intake_items(REPO)[0]['status'] == status

@pytest.mark.parametrize('change,status',[('author','needs_triage'),('empty','needs_task_spec'),('approval','human_wait')])
def test_non_ready_issues_are_not_claimed(intake,change,status):
    if change == 'author': intake[1][0]['user']['login'] = 'outsider'
    elif change == 'empty': intake[1][0]['body'] = ''
    else: intake[1][0]['labels'] = ['status:review']
    scan(intake)
    assert intake[0].intake_items(REPO)[0]['status'] == status
    assert intake[4].post('/intake/acquire',json=claim(intake),headers=AUTH).status_code == 409

def test_failed_full_read_does_not_close_known_issue(intake):
    scan(intake)
    intake[1].clear()
    async def fail(*args): raise RuntimeError('pagination failed')
    intake[3].list_open_prs = fail
    with pytest.raises(RuntimeError): scan(intake)
    assert intake[0].intake_items(REPO)[0]['status'] == 'awaiting_planner'

def test_expired_planner_is_fenced_and_new_attempt_reclaims(intake):
    store,_,_,_,client=intake
    value=claim(intake)
    assert client.post('/intake/acquire',json=value,headers=AUTH).status_code==200
    with store.conn() as db: db.execute("UPDATE issue_intake SET expires_at='2000-01-01'")
    assert client.post('/intake/heartbeat',json=value,headers=AUTH).status_code==409
    assert client.post('/intake/acquire',json=value,headers=AUTH).status_code==409
    assert client.post('/intake/acquire',json=dict(value,lease_id='attempt-token-0002'),headers=AUTH).status_code==200

def test_previously_linked_issue_never_silently_replans(intake):
    intake[2].append({'number':83,'body':'Closes #80'})
    scan(intake)
    intake[2].clear()
    intake[1][0]['body'] += ' revised'
    scan(intake)
    scan(intake)
    assert intake[0].intake_items(REPO)[0]['status'] == 'needs_link_resolution'

def test_closed_previously_linked_issue_reopen_requires_resolution(intake):
    intake[2].append({'number':83,'body':'Closes #80'})
    scan(intake)
    saved=intake[1].pop()
    intake[2].clear()
    scan(intake)
    intake[1].append(saved)
    scan(intake)
    assert intake[0].intake_items(REPO)[0]['status']=='needs_link_resolution'

def test_issue_pagination_excludes_pull_requests():
    import httpx
    from orchestrator.github_client import GitHubClient
    github=GitHubClient('test-only')
    pages=[]
    async def request(method,url,**kwargs):
        pages.append(kwargs['params']['page'])
        values=[{'number':i} for i in range(99)]+[{'number':100,'pull_request':{}}] if len(pages)==1 else [{'number':101}]
        return httpx.Response(200,json=values)
    github._request=request
    rows=asyncio.run(github.list_open_issues(REPO))
    assert len(rows)==100 and all('pull_request' not in row for row in rows)
    assert pages==[1,2]
