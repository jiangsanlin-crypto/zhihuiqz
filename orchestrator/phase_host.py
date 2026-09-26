"""Opt-in host adapter for existing account/Actions executors.

No model, GitHub mutation, subprocess, workflow dispatch or deployment is invoked
by this adapter. The host supplies its authorized cooperative executor callback.
"""

import httpx
from .claim_client import ClaimClient
from .claim_retry_journal import ClaimRetryJournal, ClaimRetriesExhausted

PHASES={'phase:prototype','phase:implementation','phase:code-review','phase:escalation-repair','phase:qa'}


async def run_one(*, url, token, repository, phase, worker_id, journal_path, execute,
                  enabled=False, transport=None, heartbeat_seconds=30):
    if phase not in PHASES:
        raise ValueError('release/deployment phases are not supported')
    if not enabled:
        return {'status':'disabled','execution_started':False}
    journal=ClaimRetryJournal(journal_path)
    client=ClaimClient(url,token,transport=transport,heartbeat_seconds=heartbeat_seconds,retry_journal=journal)
    try:
        for binding in await client.ready():
            if binding.get('repository')!=repository or binding.get('phase')!=phase:
                continue
            request=journal.next_request(binding,worker_id)
            if request is None:
                continue
            try:
                await client.acquire(binding,worker_id,request)
            except ClaimRetriesExhausted:
                continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code==409:
                    continue
                raise
            async def work():
                # Executor must use this owned binding, emit the trusted
                # exact-SHA handoff and cooperate with cancellation. All labels
                # are projected by start/advance on the server.
                return await execute(dict(client.binding),client)
            await client.run(work,advance=True)
            return {'status':'completed','execution_started':True}
        return {'status':'idle','execution_started':False}
    finally:
        await client.close()
