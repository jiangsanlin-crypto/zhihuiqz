import asyncio
import httpx
import pytest
from scripts.check_worker_service import check_service


def test_preflight_reads_both_interfaces_without_exposing_tasks_or_credentials():
    calls=[]
    async def transport(request):
        calls.append((request.method, request.url.path))
        field='candidates' if request.url.path.endswith('ready') else 'issues'
        return httpx.Response(200,json={field:[{'private':'do not log'}]})
    result=asyncio.run(check_service('https://service.test','test-only',transport=httpx.MockTransport(transport)))
    assert result['status']=='PASS' and result['execution_started'] is False
    assert calls==[('GET','/claims/ready'),('GET','/intake/issues')]
    assert 'private' not in str(result) and 'test-only' not in str(result)


@pytest.mark.parametrize('code',[301,401,404,500])
def test_endpoint_or_auth_failure_cannot_pass_or_redirect(code):
    calls=[]
    async def transport(request):
        calls.append(request)
        return httpx.Response(code,headers={'Location':'https://other.test'},json={})
    result=asyncio.run(check_service('https://service.test','test-only',transport=httpx.MockTransport(transport)))
    assert result['status']=='BLOCKED' and len(calls)==2
    assert all(request.url.host=='service.test' for request in calls)


def test_http_200_with_wrong_service_is_not_success():
    result=asyncio.run(check_service('https://service.test','test-only',transport=httpx.MockTransport(
        lambda request:httpx.Response(200,json={'ok':True}))))
    assert result['status']=='BLOCKED'
