"""Account-worker client. No GitHub mutations, subprocesses, models or dispatches.

The supplied work coroutine must cooperate with cancellation and revalidate
HEAD before each write. Publication requires a declared direct-child commit;
advancement always requires evidence for the resulting exact SHA.
"""
import asyncio
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

from .claim_retry_journal import ClaimRetriesExhausted


class LeaseLost(RuntimeError):
    pass


class ClaimClient:
    def __init__(self, url, token, *, transport=None, heartbeat_seconds=30, retry_journal=None):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('claim service requires an HTTPS URL without userinfo')
        if parsed.query or parsed.fragment or not token:
            raise ValueError('invalid claim service configuration')
        if not 0 < heartbeat_seconds <= 30:
            raise ValueError('heartbeat interval must be at most 30 seconds')
        self.client = httpx.AsyncClient(base_url=url.rstrip('/') + '/',
            headers={'Authorization': 'Bearer ' + token}, timeout=15,
            follow_redirects=False, transport=transport)
        self.interval = heartbeat_seconds
        self.ownership = None
        self.deadline = 0
        self.executed = False
        self.binding = None
        self.retry_journal = retry_journal

    async def close(self):
        await self.client.aclose()

    async def _post(self, endpoint, payload):
        response = await self.client.post('claims/' + endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    def _renew(self, result):
        expiry = datetime.fromisoformat(result['lease_expires_at'])
        remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
        # Leave margin for request latency/clock skew; never extend from a
        # stale local timestamp. The server still fences every write.
        self.deadline = time.monotonic() + min(120, remaining - 30)
        if self.deadline <= time.monotonic():
            raise LeaseLost('claim response is already too close to expiry')

    async def ready(self):
        response = await self.client.get('claims/ready')
        response.raise_for_status()
        return response.json()['candidates']

    async def consume_one(self, phase, worker_id, work):
        """Wire a cooperative account worker to discovery and ownership.

        work(binding) must publish its trusted exact-SHA handoff before return.
        Code-changing phases must use publish_head and fresh final-SHA evidence.
        """
        if phase not in {'phase:implementation', 'phase:code-review', 'phase:escalation-repair'}:
            raise ValueError('only account-owned phases may use this consumer')
        for binding in await self.ready():
            if binding['phase'] != phase:
                continue
            request_id = (self.retry_journal.next_request(binding, worker_id)
                          if self.retry_journal else str(uuid.uuid4()))
            if request_id is None:
                continue  # Persisted failure cooldown; fresh discovery reevaluates later.
            try:
                await self.acquire(binding, worker_id, request_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 409:
                    continue  # Another worker or a newer live state won.
                raise
            return await self.run(lambda: work(self.binding), advance=True)
        return None

    async def acquire(self, binding, worker_id, request_id, delays=(0, 120, 300, 600, 1200)):
        if self.ownership:
            raise LeaseLost('client already owns a claim')
        value = dict(binding, worker_id=worker_id, request_id=request_id)
        if not delays:
            raise ValueError('retry schedule must not be empty')
        journal = self.retry_journal
        previous = journal.attempts(binding, worker_id, request_id) if journal else []
        if previous and previous[-1]['status'] in {'exhausted', 'stale'}:
            raise ClaimRetriesExhausted('attempt ended; fresh state evaluation is required')
        # Resume an uncertain request at the same index; a recorded retryable
        # failure advances the budget. Restarts cannot reset exhausted attempts.
        start = previous[-1]['attempt'] if previous else 0
        if previous and previous[-1]['status'] == 'retryable':
            start += 1
        def record(index, status, code=''):
            if journal:
                journal.record(binding, worker_id, request_id, index, status, code)
        # Retry the SAME request ID. Every server attempt refreshes GitHub.
        for index, delay in enumerate(delays):
            if index < start:
                continue
            if delay:
                await asyncio.sleep(delay)
            record(index, 'attempting')
            try:
                result = await self._post('acquire', value)
                self._renew(result)
                self.ownership = dict(delivery_id=result['delivery_id'],
                    lease_id=result['lease_id'], worker_id=worker_id)
                self.binding = dict(binding)
                record(index, 'acquired')
                return result
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 and exc.response.status_code < 500:
                    record(index, 'stale', 'STATE_OR_AUTH')
                    raise  # Includes 401 and all stale-state/ownership 409s.
                record(index, 'exhausted' if index == len(delays)-1 else 'retryable',
                       'WORKER_ACQUISITION_FAILED' if index == len(delays)-1 else 'HTTP_RETRYABLE')
                if index == len(delays) - 1:
                    raise
            except httpx.TransportError:
                record(index, 'exhausted' if index == len(delays)-1 else 'retryable',
                       'WORKER_ACQUISITION_FAILED' if index == len(delays)-1 else 'TRANSPORT')
                if index == len(delays) - 1:
                    raise
        raise ValueError('retry schedule must not be empty')

    async def _owned(self, endpoint):
        if not self.ownership or time.monotonic() >= self.deadline:
            raise LeaseLost('worker lease is unavailable or expired')
        try:
            return await asyncio.wait_for(self._post(endpoint, self.ownership),
                timeout=min(15, self.deadline - time.monotonic()))
        except Exception as exc:
            # An uncertain heartbeat is not permission to keep writing.
            self.deadline = 0
            raise LeaseLost('lease operation failed; stop worker') from exc

    async def publish_head(self, target_sha, publish):
        """Declare an immutable direct child, then let the host publish its ref.

        publish() must perform an exact-parent, non-forced PR-head update and
        obey cancellation. It must not create or modify the declared commit.
        """
        if not self.ownership or time.monotonic() >= self.deadline:
            raise LeaseLost('worker lease is unavailable or expired')
        try:
            await asyncio.wait_for(self._post('prepare-head',
                dict(self.ownership, target_sha=target_sha)),
                timeout=min(15, self.deadline - time.monotonic()))
            await asyncio.wait_for(publish(), timeout=max(0, self.deadline - time.monotonic()))
            result = await self._owned('confirm-head')
            self._renew(result)
            if self.binding is not None:
                self.binding['source_sha'] = result['source_sha']
            return result['source_sha']
        except Exception as exc:
            self.deadline = 0
            raise LeaseLost('publication uncertain; stop worker and allow recovery') from exc

    async def run(self, work, *, advance=False):
        if self.executed:
            raise LeaseLost('this client already attempted phase execution')
        self.executed = True
        started = await self._owned('start')
        self._renew(started)

        async def monitor():
            while True:
                await asyncio.sleep(self.interval)
                self._renew(await self._owned('heartbeat'))

        heartbeat = asyncio.create_task(monitor())
        task = asyncio.create_task(work())
        try:
            completed, _ = await asyncio.wait({heartbeat, task}, return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in completed:
                await heartbeat  # Propagate failure before using a worker result.
                raise LeaseLost('heartbeat stopped unexpectedly')
            result = await task
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            self._renew(await self._owned('heartbeat'))
            if advance:
                await self._owned('advance')
                self.ownership = None
                self.deadline = 0
            return result
        finally:
            # No label requeue or fake PASS on failure. Durable server recovery
            # must examine the actual phase result before reclaiming RUNNING.
            task.cancel()
            heartbeat.cancel()
            await asyncio.gather(task, heartbeat, return_exceptions=True)
