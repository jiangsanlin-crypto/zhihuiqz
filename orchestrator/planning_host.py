"""Opt-in cooperative host for resuming an immutable unpublished plan."""
import asyncio
import time
import uuid
import httpx
from .claim_client import ClaimClient,LeaseLost


async def resume_one(*,url,token,worker_id,publish,enabled=False,transport=None,heartbeat_seconds=30):
    if not enabled:return {'status':'disabled','execution_started':False}
    # Reuse the HTTPS/no-redirect transport validation, not phase execution.
    connection=ClaimClient(url,token,transport=transport,heartbeat_seconds=heartbeat_seconds)
    client=connection.client
    try:
        response=await client.get('intake/publications');response.raise_for_status()
        for saved in response.json()['publications']:
            if saved['status']!='prepared':continue
            intent=saved['intent']
            claim=dict(issue_number=intent['issue_number'],generation=intent['generation'],
                       worker_id=worker_id,lease_id=str(uuid.uuid4()))
            request=dict(claim,publication_id=saved['publication_id'])
            response=await client.post('intake/resume-publication',json=request)
            if response.status_code==409:continue
            response.raise_for_status();receipt=response.json()
            deadline=time.monotonic()+120
            async def guard():
                nonlocal deadline
                if time.monotonic()>=deadline:raise LeaseLost('planning lease uncertain')
                try:
                    response=await client.post('intake/heartbeat',json=claim)
                    response.raise_for_status()
                    if response.json().get('renewed') is not True:raise ValueError('renewal missing')
                    deadline=time.monotonic()+120
                except Exception as exc:raise LeaseLost('planning lease lost') from exc
            async def monitor():
                while True:
                    await asyncio.sleep(heartbeat_seconds)
                    await guard()
            # The host must reproduce the declared artifact/body, recheck branch
            # and existing PRs, call guard before writes, and never force-push.
            await guard()
            task=asyncio.create_task(publish(receipt,guard))
            heartbeat=asyncio.create_task(monitor())
            try:
                completed,_=await asyncio.wait({task,heartbeat},return_when=asyncio.FIRST_COMPLETED)
                if heartbeat in completed:
                    await heartbeat
                    raise LeaseLost('planning monitor stopped')
                number=await task
                if type(number) is not int or number<=0:raise ValueError('publisher must return PR number')
                heartbeat.cancel();await asyncio.gather(heartbeat,return_exceptions=True)
                result=await client.post('intake/confirm-publication',json=dict(request,pr_number=number))
                result.raise_for_status()
                return {'status':'confirmed','execution_started':True,'pr_number':number}
            finally:
                task.cancel();heartbeat.cancel()
                await asyncio.gather(task,heartbeat,return_exceptions=True)
        return {'status':'idle','execution_started':False}
    finally:
        await connection.close()
