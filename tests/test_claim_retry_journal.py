import asyncio
import httpx
import pytest

from orchestrator.claim_client import ClaimClient
from orchestrator.claim_retry_journal import ClaimRetryJournal, ClaimRetriesExhausted
from test_claim_client import lease


def test_exhaustion_survives_host_restart_without_resetting_budget(tmp_path):
    path=tmp_path/'retry.db'
    calls=[]
    async def transport(request):
        calls.append(request)
        raise httpx.ConnectError('sensitive error detail',request=request)
    async def run():
        first=ClaimClient('https://service.test','test-only',retry_journal=ClaimRetryJournal(path),transport=httpx.MockTransport(transport))
        with pytest.raises(httpx.ConnectError):
            await first.acquire({'source_sha':'a'*40},'worker','request',delays=(0,0,0))
        await first.close()
        second=ClaimClient('https://service.test','test-only',retry_journal=ClaimRetryJournal(path),transport=httpx.MockTransport(transport))
        with pytest.raises(ClaimRetriesExhausted):
            await second.acquire({'source_sha':'a'*40},'worker','request',delays=(0,0,0))
        await second.close()
    asyncio.run(run())
    rows=ClaimRetryJournal(path).attempts({'source_sha':'a'*40},'worker','request')
    assert len(calls)==3 and rows[-1]['status']=='exhausted'
    assert rows[-1]['error_code']=='WORKER_ACQUISITION_FAILED'
    assert 'sensitive' not in str(rows) and 'test-only' not in str(rows)


def test_recorded_failure_resumes_remaining_attempts(tmp_path):
    journal=ClaimRetryJournal(tmp_path/'retry.db')
    binding={'source_sha':'a'*40}
    journal.record(binding,'worker','request',0,'retryable','TRANSPORT')
    calls=[]
    async def transport(request):
        calls.append(request)
        return httpx.Response(200,json=lease())
    async def run():
        client=ClaimClient('https://service.test','test-only',retry_journal=journal,transport=httpx.MockTransport(transport))
        await client.acquire(binding,'worker','request',delays=(0,0,0))
        await client.close()
    asyncio.run(run())
    assert len(calls)==1
    assert [(r['attempt'],r['status']) for r in journal.attempts(binding,'worker','request')]==[(0,'retryable'),(1,'acquired')]


def test_changed_binding_cannot_reuse_request(tmp_path):
    journal=ClaimRetryJournal(tmp_path/'retry.db')
    journal.record({'sha':'a'},'w','r',0,'attempting')
    with pytest.raises(ValueError,match='change binding'):
        journal.record({'sha':'b'},'w','r',1,'attempting')
    with pytest.raises(ValueError,match='change binding'):
        journal.attempts({'sha':'b'},'w','r')


@pytest.mark.parametrize('code',[401,409])
def test_stale_or_auth_failure_is_durable_and_never_retried(tmp_path,code):
    journal=ClaimRetryJournal(tmp_path/'retry.db')
    calls=[]
    async def transport(request):
        calls.append(request)
        return httpx.Response(code,json={})
    async def run():
        client=ClaimClient('https://service.test','test-only',retry_journal=journal,transport=httpx.MockTransport(transport))
        with pytest.raises(httpx.HTTPStatusError):
            await client.acquire({},'w','r',delays=(0,0))
        with pytest.raises(ClaimRetriesExhausted):
            await client.acquire({},'w','r',delays=(0,0))
        await client.close()
    asyncio.run(run())
    assert len(calls)==1 and journal.attempts({},'w','r')[-1]['status']=='stale'


def test_fresh_discovery_cannot_reset_cooldown_but_later_recovers(tmp_path):
    from datetime import datetime, timedelta, timezone
    journal=ClaimRetryJournal(tmp_path/'retry.db')
    binding={'source_sha':'a'*40}
    journal.record(binding,'w','old',4,'exhausted','WORKER_ACQUISITION_FAILED')
    assert journal.next_request(binding,'w') is None
    later=datetime.now(timezone.utc)+timedelta(seconds=601)
    assert journal.next_request(binding,'w',timestamp=later) not in {None,'old'}
    assert journal.next_request({'source_sha':'b'*40},'w') is not None
    journal.record(binding,'w','new',0,'retryable','TRANSPORT')
    assert journal.next_request(binding,'w')=='new'


def test_consumer_skips_exhausted_binding_without_remote_acquisition(tmp_path):
    journal=ClaimRetryJournal(tmp_path/'retry.db')
    binding={'source_sha':'a'*40,'phase':'phase:code-review'}
    journal.record(binding,'w','old',4,'exhausted','WORKER_ACQUISITION_FAILED')
    paths=[]
    async def transport(request):
        paths.append(request.url.path)
        return httpx.Response(200,json={'candidates':[binding]})
    async def run():
        client=ClaimClient('https://service.test','test-only',retry_journal=journal,transport=httpx.MockTransport(transport))
        async def work(binding): raise AssertionError('must not execute')
        assert await client.consume_one('phase:code-review','w',work) is None
        await client.close()
    asyncio.run(run())
    assert paths==['/claims/ready']
