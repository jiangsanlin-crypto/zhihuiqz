import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from orchestrator import control_api
from orchestrator.control_api import create_control_router
from orchestrator.state_store import StateStore
from scripts.shared_workflow_entry import wake

SHA='a'*40
AUTH={'Authorization':'Bearer test-only'}

def setup_api(tmp_path,monkeypatch,steps):
    store=StateStore(str(tmp_path/'state.db'))
    monkeypatch.setattr(control_api,'STEPS',steps)
    app=FastAPI();app.include_router(create_control_router(store,SimpleNamespace(),
        SimpleNamespace(github_repository='owner/repo',orchestrator_token='test-only'),SHA))
    return store,TestClient(app)

def request(**extra):return dict(repository='owner/repo',expected_build_sha=SHA,source='watchdog',delivery_id='actions:1:1',**extra)

def test_wake_auth_build_fence_and_idempotent_receipt(tmp_path,monkeypatch):
    calls=[]
    async def scan(*args):calls.append(True);return 2
    store,client=setup_api(tmp_path,monkeypatch,(scan,))
    assert client.post('/control/wake',json=request()).status_code==401
    assert client.post('/control/wake',json=dict(request(),expected_build_sha='b'*40),headers=AUTH).status_code==409
    for _ in range(2):
        result=client.post('/control/wake',json=request(),headers=AUTH)
        assert result.status_code==200 and result.json()['execution_started'] is False
    assert calls==[True]

def test_step_failure_is_retryable_and_cannot_report_success(tmp_path,monkeypatch):
    calls=[]
    async def scan(*args):
        calls.append(True)
        if len(calls)==1:raise RuntimeError('private error')
        return 1
    _,client=setup_api(tmp_path,monkeypatch,(scan,))
    result=client.post('/control/wake',json=request(),headers=AUTH)
    assert result.status_code==503 and 'private' not in result.text
    assert client.post('/control/wake',json=request(),headers=AUTH).status_code==200

def test_bridge_never_falls_back_to_github_or_redirects():
    paths=[]
    def transport(req):
        paths.append(str(req.url))
        return httpx.Response(302,headers={'Location':'https://other.test'},json={})
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(wake(url='https://control.test',token='test-only',repository='owner/repo',expected_sha=SHA,
            source='watchdog',delivery_id='actions:1',transport=httpx.MockTransport(transport)))
    assert paths==['https://control.test/readyz']

def test_bridge_validates_identity_before_posting():
    paths=[]
    def transport(req):
        paths.append(req.url.path)
        if req.method=='GET':return httpx.Response(200,json=dict(repository='owner/repo',build_sha=SHA,
            protocol='shared-claims:v1',writes_enabled=True,agents_enabled=False))
        assert json.loads(req.content)['expected_build_sha']==SHA
        return httpx.Response(200,json=dict(status='completed',execution_started=False,dispatch_performed=False))
    result=asyncio.run(wake(url='https://control.test',token='test-only',repository='owner/repo',expected_sha=SHA,
        source='planner',delivery_id='actions:1',transport=httpx.MockTransport(transport)))
    assert result['status']=='CONTROLLER_ACKNOWLEDGED'
    assert paths==['/readyz','/control/wake']

@pytest.mark.parametrize('name,legacy',[
 ('openai-validator.yml',['validate']),('codex-task.yml',['product-plan','release-review']),
 ('handoff-reconciler.yml',['reconcile']),('agent-watchdog.yml',['watchdog'])])
def test_workflow_migration_is_exclusive_read_only_and_revision_pinned(name,legacy):
    import yaml
    data=yaml.safe_load((Path('.github/workflows')/name).read_text())
    jobs=data['jobs'];shared=jobs['shared-control']
    assert shared['if']=="(vars.CONTROL_WORKFLOW_MODE == '' || vars.CONTROL_WORKFLOW_MODE == 'shared')"
    assert shared['permissions']=={'contents':'read'}
    assert jobs['invalid-control-mode']['permissions']=={}
    for old in legacy:
        assert "vars.CONTROL_WORKFLOW_MODE == 'legacy'" in jobs[old]['if']
    checkout=next(s for s in shared['steps'] if s.get('uses','').startswith('actions/checkout'))
    assert checkout['with']['ref']=='${{ vars.CONTROL_BUILD_SHA || github.sha }}'
    text=json.dumps(shared)
    for forbidden in ['gh api','gh pr','codex-action','OPENAI_API_KEY','repository_dispatch','workflow_dispatch','continue-on-error']:
        assert forbidden not in text
    assert 'shared_workflow_entry.py' in text


def test_active_tick_excludes_concurrent_workflow(tmp_path,monkeypatch):
    async def scan(*args):return 0
    store,client=setup_api(tmp_path,monkeypatch,(scan,))
    with store.conn() as db:
        db.execute("INSERT INTO control_requests VALUES('owner/repo','other','planner','running','2999-01-01',NULL)")
    assert client.post('/control/wake',json=request(),headers=AUTH).status_code==409

@pytest.mark.parametrize('body',[[],{},'wrong service'])
def test_malformed_readiness_never_posts(body):
    methods=[]
    def transport(req):methods.append(req.method);return httpx.Response(200,json=body)
    with pytest.raises(ValueError):asyncio.run(wake(url='https://control.test',token='test-only',repository='owner/repo',
        expected_sha=SHA,source='watchdog',delivery_id='actions:1',transport=httpx.MockTransport(transport)))
    assert methods==['GET']


def test_tick_lease_loss_cannot_publish_success(tmp_path,monkeypatch):
    holder={}
    async def scan(*args):
        with holder['store'].conn() as db:db.execute("UPDATE control_requests SET expires_at='2000-01-01'")
        return 1
    store,client=setup_api(tmp_path,monkeypatch,(scan,));holder['store']=store
    assert client.post('/control/wake',json=request(),headers=AUTH).status_code==409
    with store.conn() as db:assert db.execute('SELECT status FROM control_requests').fetchone()[0]=='running'
