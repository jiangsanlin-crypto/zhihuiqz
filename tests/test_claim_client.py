import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from orchestrator.claim_client import ClaimClient, LeaseLost


def lease():
    return {'delivery_id': 'd', 'lease_id': 'l',
            'lease_expires_at': (datetime.now(timezone.utc) + timedelta(seconds=180)).isoformat()}


def test_uncertain_acquisition_reuses_request_id_and_advances_with_heartbeat():
    calls, bodies = [], []
    async def transport(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/acquire'):
            bodies.append(json.loads(request.content))
            if len(bodies) == 1: raise httpx.ConnectError('test', request=request)
        return httpx.Response(200, json=lease())
    async def run():
        client = ClaimClient('https://claims.test', 'test-only', transport=httpx.MockTransport(transport))
        await client.acquire({'phase': 'phase:code-review'}, 'worker', 'stable', delays=(0, 0))
        async def work(): return 'done'
        assert await client.run(work, advance=True) == 'done'
        assert client.ownership is None
        await client.close()
    asyncio.run(run())
    assert bodies[0] == bodies[1]
    assert calls[-3:] == ['/claims/start', '/claims/heartbeat', '/claims/advance']


@pytest.mark.parametrize('code', [401, 409])
def test_auth_or_stale_state_is_not_retried(code):
    calls = []
    async def transport(request):
        calls.append(request)
        return httpx.Response(code, json={})
    async def run():
        client = ClaimClient('https://claims.test', 'test-only', transport=httpx.MockTransport(transport))
        with pytest.raises(httpx.HTTPStatusError):
            await client.acquire({}, 'worker', 'stable', delays=(0, 0))
        await client.close()
    asyncio.run(run())
    assert len(calls) == 1


def test_heartbeat_failure_cancels_work_and_never_advances():
    calls, cancelled = [], []
    async def transport(request):
        calls.append(request.url.path)
        return httpx.Response(409 if request.url.path.endswith('/heartbeat') else 200, json=lease())
    async def run():
        client = ClaimClient('https://claims.test', 'test-only', transport=httpx.MockTransport(transport), heartbeat_seconds=.001)
        await client.acquire({}, 'worker', 'stable', delays=(0,))
        async def work():
            try: await asyncio.Event().wait()
            finally: cancelled.append(True)
        with pytest.raises(LeaseLost): await client.run(work, advance=True)
        await client.close()
    asyncio.run(run())
    assert cancelled == [True]
    assert '/claims/advance' not in calls


def test_expired_lease_cannot_start_worker():
    calls = []
    async def transport(request):
        calls.append(request.url.path)
        result = lease()
        result['lease_expires_at'] = '2000-01-01T00:00:00+00:00'
        return httpx.Response(200, json=result)
    async def run():
        client = ClaimClient('https://claims.test', 'test-only', transport=httpx.MockTransport(transport))
        with pytest.raises(LeaseLost): await client.acquire({}, 'worker', 'stable', delays=(0,))
        await client.close()
    asyncio.run(run())
    assert calls == ['/claims/acquire']


def test_account_consumer_skips_busy_work_and_never_invokes_api_phase():
    calls, executed = [], []
    async def transport(request):
        path = request.url.path
        calls.append(path)
        if path.endswith('/ready'):
            return httpx.Response(200, json={'candidates': [
                {'phase': 'phase:qa', 'pr_number': 1},
                {'phase': 'phase:code-review', 'pr_number': 2},
                {'phase': 'phase:code-review', 'pr_number': 3}]})
        if path.endswith('/acquire') and json.loads(request.content)['pr_number'] == 2:
            return httpx.Response(409, json={'detail': 'ANOTHER_WORKER_OWNS_LEASE'})
        return httpx.Response(200, json=lease())
    async def run():
        client = ClaimClient('https://claims.test', 'test-only', transport=httpx.MockTransport(transport))
        async def work(binding):
            executed.append(binding['pr_number'])
            return 'reviewed'
        assert await client.consume_one('phase:code-review', 'account-worker', work) == 'reviewed'
        with pytest.raises(ValueError): await client.consume_one('phase:qa', 'account-worker', work)
        await client.close()
    asyncio.run(run())
    assert executed == [3]
    assert calls.count('/claims/advance') == 1
