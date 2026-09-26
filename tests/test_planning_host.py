import asyncio
import httpx
import pytest
from orchestrator.planning_host import resume_one
from test_publication_resume import resumable
from test_planning_publication import publication
from test_issue_intake import intake


def test_replacement_host_resumes_and_confirms_through_real_service(resumable):
    data,_,_=resumable;client=data[0][-1];calls=[]
    async def publish(receipt,guard):
        await guard()
        assert receipt['intent']['head_ref']=='plans/issue-80'
        calls.append(receipt['publication_id'])
        data[0][2].append(dict(number=83,state='open',body=data[3],labels=[],base={'ref':'main'},
            head={'ref':'plans/issue-80','sha':'a'*40,'repo':{'full_name':'owner/repo'}}))
        return 83
    async def run():
        return await resume_one(url='https://claims.test',token='test-only',worker_id='replacement',
            publish=publish,enabled=True,transport=httpx.ASGITransport(app=client.app))
    assert asyncio.run(run())['status']=='confirmed'
    assert asyncio.run(run())['status']=='idle'
    assert len(calls)==1

def test_active_owner_prevents_new_host_execution(resumable):
    data,_,_=resumable
    with data[0][0].conn() as db:db.execute("UPDATE issue_intake SET expires_at='2999-01-01'")
    async def forbidden(*args):raise AssertionError('must not execute')
    result=asyncio.run(resume_one(url='https://claims.test',token='test-only',worker_id='replacement',
        publish=forbidden,enabled=True,transport=httpx.ASGITransport(app=data[0][-1].app)))
    assert result['status']=='idle'

def test_planning_host_default_disabled_has_no_network():
    async def forbidden(*args):raise AssertionError('must not execute')
    assert asyncio.run(resume_one(url='',token='',worker_id='w',publish=forbidden))['status']=='disabled'
