import asyncio
import json
import httpx
import pytest
from orchestrator.phase_host import run_one,PHASES
from orchestrator.claim_client import LeaseLost
from test_claim_client import lease


def options(tmp_path,transport,execute,**extra):
    return dict(url='https://claims.test',token='test-only',repository='owner/repo',
        phase='phase:code-review',worker_id='account-worker',journal_path=tmp_path/'attempts.db',
        execute=execute,transport=httpx.MockTransport(transport),**extra)


def test_default_disabled_performs_no_discovery_or_execution(tmp_path):
    def forbidden(*args):raise AssertionError('must not run')
    result=asyncio.run(run_one(**options(tmp_path,forbidden,forbidden)))
    assert result=={'status':'disabled','execution_started':False}
    assert not (tmp_path/'attempts.db').exists()

@pytest.mark.parametrize('phase',sorted(PHASES))
def test_all_supported_hosts_use_service_owned_transitions(tmp_path,phase):
    calls=[];executions=[]
    binding=dict(repository='owner/repo',phase=phase,pr_number=83,source_sha='a'*40)
    def transport(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/ready'):
            return httpx.Response(200,json={'candidates':[dict(binding,repository='other/repo'),binding]})
        if request.url.path.endswith('/acquire'):
            assert json.loads(request.content)['repository']=='owner/repo'
        return httpx.Response(200,json=lease())
    async def execute(owned,client):
        assert calls[-1]=='/claims/start'
        executions.append(owned)
    opts=options(tmp_path,transport,execute,enabled=True);opts['phase']=phase
    assert asyncio.run(run_one(**opts))['status']=='completed'
    assert executions==[binding]
    assert calls==['/claims/ready','/claims/acquire','/claims/start','/claims/heartbeat','/claims/advance']


def test_denied_start_never_executes(tmp_path):
    paths=[]
    def transport(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/ready'):
            return httpx.Response(200,json={'candidates':[{'repository':'owner/repo','phase':'phase:code-review'}]})
        return httpx.Response(409 if request.url.path.endswith('/start') else 200,json=lease())
    async def execute(*args):raise AssertionError('must not execute')
    with pytest.raises(LeaseLost):asyncio.run(run_one(**options(tmp_path,transport,execute,enabled=True)))
    assert '/claims/advance' not in paths


def test_lost_heartbeat_cancels_actions_executor(tmp_path):
    stopped=[];paths=[]
    def transport(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/ready'):
            return httpx.Response(200,json={'candidates':[{'repository':'owner/repo','phase':'phase:qa'}]})
        return httpx.Response(409 if request.url.path.endswith('/heartbeat') else 200,json=lease())
    async def execute(*args):
        try:await asyncio.Event().wait()
        finally:stopped.append(True)
    opts=options(tmp_path,transport,execute,enabled=True,heartbeat_seconds=.001);opts['phase']='phase:qa'
    with pytest.raises(LeaseLost):asyncio.run(run_one(**opts))
    assert stopped==[True] and '/claims/advance' not in paths

from test_claim_api import setup,projection_setup


def test_host_uses_real_service_and_shared_writer(projection_setup,tmp_path):
    import copy
    client,store,pr,github,_,_,writes=projection_setup
    pr['number']=78
    async def listing(*args):return [copy.deepcopy(pr)]
    github.list_open_prs=listing
    async def execute(binding,owned_client):
        assert 'status:running' in pr['labels']
        assert binding['source_sha']==pr['head']['sha']
    result=asyncio.run(run_one(url='https://claims.test',token='test-only-token',repository='owner/repo',
        phase='phase:code-review',worker_id='host',journal_path=tmp_path/'host.db',execute=execute,
        enabled=True,transport=httpx.ASGITransport(app=client.app)))
    assert result['status']=='completed'
    assert pr['labels']==['agent:workbuddy','phase:qa','status:todo']
    assert len(writes)==2
    with store.conn() as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE status='running'").fetchone()[0]==0
