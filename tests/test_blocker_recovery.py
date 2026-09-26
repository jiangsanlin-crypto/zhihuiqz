import asyncio
import copy
import json

import pytest

from test_claim_api import setup, projection_setup, expire_claim, SHA
from orchestrator.blocker_recovery import recover_blockers_once
from orchestrator.external_recovery import recover_external_once
from orchestrator.queue_discovery import scan_once

@pytest.fixture
def blocked(projection_setup):
    _,store,pr,github,comments,runs,writes=projection_setup
    pr['number']=78
    pr['labels']=['agent:workbuddy','phase:qa','status:blocked','recovery:qa-evidence']
    async def listing(*args): return [copy.deepcopy(pr)]
    github.list_open_prs=listing
    return store,pr,github,comments,runs,writes

def recover(data):
    return asyncio.run(recover_blockers_once(data[0],data[2],'owner/repo'))

def observation(store):
    with store.conn() as db:
        return json.loads(db.execute('SELECT payload_json FROM blocker_observations').fetchone()[0])

def test_current_sha_review_and_ci_resolve_once(blocked):
    assert recover(blocked)==1
    assert 'status:todo' in blocked[1]['labels']
    assert observation(blocked[0])['status']=='resolved'
    assert recover(blocked)==0
    assert len(blocked[-1])==1

@pytest.mark.parametrize('missing',['ci','review','old_sha','unknown','human'])
def test_insufficient_evidence_and_human_wait_preserved(blocked,missing):
    if missing=='ci': blocked[4]['workflow_runs'][0]['conclusion']='failure'
    elif missing=='review': blocked[3].clear()
    elif missing=='old_sha': blocked[1]['head']['sha']='b'*40
    elif missing=='unknown': blocked[1]['labels'][-1]='blocker:content'
    else: blocked[1]['labels'].append('approval:production-required')
    original=copy.deepcopy(blocked[1])
    assert recover(blocked)==0
    assert blocked[1]==original and not blocked[-1]

def test_human_wait_added_during_evidence_read_is_not_overwritten(blocked):
    async def runs(*args):
        blocked[1]['labels'].append('approval:production-required')
        return copy.deepcopy(blocked[4])
    blocked[2].list_workflow_runs=runs
    assert recover(blocked)==0
    assert 'approval:production-required' in blocked[1]['labels']
    assert not blocked[-1]

def test_lost_put_response_recovered_from_durable_checkpoint(blocked):
    store,pr,github,_,_,writes=blocked
    original=github.set_labels
    async def lose(*args):
        await original(*args)
        raise RuntimeError('response lost')
    github.set_labels=lose
    with pytest.raises(RuntimeError): recover(blocked)
    with store.conn() as db:
        delivery=db.execute("SELECT delivery_id FROM events WHERE status='running'").fetchone()[0]
    expire_claim(store,delivery)
    assert asyncio.run(recover_external_once(store,github,'owner/repo'))==1
    assert observation(store)['status']=='resolved'
    assert len(writes)==1
    assert store.queue_generation(dict(repository='owner/repo',pr_number=78,source_sha=SHA,phase='phase:qa'))!='initial'

def test_recovery_requeues_previously_consumed_same_sha(blocked):
    store,pr,github,_,_,_=blocked
    original=pr['labels'][:]
    pr['labels']=['agent:workbuddy','phase:qa','status:todo']
    assert asyncio.run(scan_once(store,github,'owner/repo'))==1
    row=store.claim_next()
    store.finish(row['delivery_id'],'done',lease_id=row['lease_id'])
    pr['labels']=original
    assert recover(blocked)==1
    assert asyncio.run(scan_once(store,github,'owner/repo'))==1
    assert asyncio.run(scan_once(store,github,'owner/repo'))==0

@pytest.mark.parametrize('record_sha,mergeable,expected',[(SHA,'clean',1),('b'*40,'clean',0),(SHA,'unknown',0),(SHA,'dirty',0)])
def test_repair_requires_exact_sha_and_verified_mergeability(blocked,record_sha,mergeable,expected):
    _,pr,_,comments,_,_=blocked
    pr['labels']=['agent:workreview','phase:escalation-repair','status:blocked','recovery:repair-ci']
    pr['mergeable_state']=mergeable
    comments[:]=[{'id':3,'created_at':'2026-09-26T01:00:00Z','user':{'login':'owner'},'body':
        '<!-- agent-repair:v1 -->\nphase=escalation-repair\nstatus=waiting_exact_sha_ci\nsource_sha='+record_sha}]
    assert recover(blocked)==expected
    if expected:
        assert 'phase:code-review' in pr['labels'] and 'status:todo' in pr['labels']
        assert 'phase:qa' not in pr['labels']
    else:
        assert not blocked[-1]
