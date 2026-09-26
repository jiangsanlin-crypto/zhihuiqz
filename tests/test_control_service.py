from types import SimpleNamespace

from fastapi.testclient import TestClient

from orchestrator.control_service import create_app, secret_file
from orchestrator.state_store import StateStore


def test_default_preflight_has_no_worker_or_mutation_and_requires_auth(tmp_path):
    calls=[]
    async def prs(repo):
        calls.append(repo)
        return []
    app=create_app(store=StateStore(str(tmp_path/'db')),github=SimpleNamespace(list_open_prs=prs),
        settings=SimpleNamespace(github_repository='owner/repo',orchestrator_token='test-only'),
        writes_enabled=False,build_sha='a'*40)
    with TestClient(app) as client:
        assert calls==[]
        assert client.get('/readyz').json()==dict(status='ready',build_sha='a'*40,writes_enabled=False,agents_enabled=False,repository='owner/repo',protocol='shared-claims:v1')
        assert client.get('/claims/ready').status_code==401
        assert client.get('/intake/issues').status_code==401
        assert client.post('/claims/acquire').status_code==503
        assert client.post('/intake/acquire').status_code==503
        assert client.get('/claims/ready',headers={'Authorization':'Bearer test-only'}).json()=={'candidates':[]}
        assert calls==['owner/repo']
        assert client.post('/webhook/github').status_code==503
        assert client.get('/docs').status_code==404


def test_secret_file_rejects_blank_or_multiline_without_echoing_value(tmp_path):
    import pytest
    path=tmp_path/'credential'
    for value in ['', 'short', 'a'*40+'\n'+'b'*40]:
        path.write_text(value)
        with pytest.raises(ValueError,match='invalid control-service credential file'):
            secret_file(path)
    path.write_text('a'*48+'\n')
    assert secret_file(path)=='a'*48


def test_active_controller_never_enqueues_work_without_executor(tmp_path, monkeypatch):
    import asyncio
    from orchestrator import control_service
    observed=[]
    async def scan(stop,store,github,repository,*,native_queue):
        observed.append(native_queue)
        await stop.wait()
    monkeypatch.setattr(control_service,'discovery_loop',scan)
    app=create_app(store=StateStore(str(tmp_path/'db')),github=SimpleNamespace(),
        settings=SimpleNamespace(github_repository='owner/repo',orchestrator_token='test-only'),
        writes_enabled=True,build_sha='a'*40)
    with TestClient(app) as client:
        assert client.get('/readyz').json()['agents_enabled'] is False
    assert observed==[False]


def test_read_only_flag_cannot_be_changed_by_request(tmp_path):
    app=create_app(store=StateStore(str(tmp_path/'db')),github=SimpleNamespace(),
        settings=SimpleNamespace(github_repository='owner/repo',orchestrator_token='test-only'),
        writes_enabled=False,build_sha='a'*40)
    with TestClient(app) as client:
        for method in ('post','put','patch','delete'):
            response=getattr(client,method)('/claims/start?CONTROL_WRITES_ENABLED=true',headers={'Authorization':'Bearer test-only'})
            assert response.status_code==503
        assert client.get('/readyz').json()['writes_enabled'] is False


def test_build_identity_required(tmp_path):
    import pytest
    with pytest.raises(ValueError,match='reviewed commit'):
        create_app(store=StateStore(str(tmp_path/'db')),github=SimpleNamespace(),
            settings=SimpleNamespace(github_repository='owner/repo',orchestrator_token='test-only'),
            writes_enabled=False,build_sha='latest')
