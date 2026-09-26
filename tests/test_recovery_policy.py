import asyncio
import copy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import pytest
from orchestrator.recovery_policy import timeout_action
from orchestrator.timeout_monitor import monitor_timeouts
from orchestrator.state_store import StateStore
from test_queue_discovery import pr

@pytest.mark.parametrize('status,age,action',[
 ('todo',899,'none'),('todo',900,'warn_ready'),('todo',1799,'warn_ready'),
 ('todo',1800,'scan_consumer'),('todo',3600,'recovery_scan_p1'),
 ('running',1199,'none'),('running',1200,'warn_running'),
 ('running',1800,'verify_progress'),('running',3600,'reclaim')])
def test_exact_boundaries(status,age,action):
    assert timeout_action(status,age,tracked=True)==action

def test_human_wait_live_lease_and_unknown_ownership_are_not_reclaimed():
    assert timeout_action('running',7200,human_wait=True)=='none'
    assert timeout_action('running',7200,live_lease=True,tracked=True)=='verify_progress'
    assert timeout_action('running',7200)=='ownership_verification_required'
    assert timeout_action('running',7200,tracked=True,durable_result=True)=='reconcile_result'

def test_persistent_audit_deduplicates_and_human_wait_closes_episode(tmp_path):
    store=StateStore(str(tmp_path/'state.db'));values=[pr()]
    async def listing(*args):return copy.deepcopy(values)
    github=SimpleNamespace(list_open_prs=listing)
    def scan(db):return asyncio.run(monitor_timeouts(db,github,'owner/repo'))
    assert scan(store)==0
    with store.conn() as db:
        db.execute('UPDATE timeout_observations SET first_seen=?',((datetime.now(timezone.utc)-timedelta(minutes=61)).isoformat(),))
    assert scan(store)==1
    restarted=StateStore(store.path)
    assert scan(restarted)==0
    values[0]['labels']=['status:review','approval:production-required']
    assert scan(restarted)==0
    with store.conn() as db:
        assert db.execute('SELECT active FROM timeout_observations').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM timeout_audit').fetchone()[0]==1
    values[0]=pr()
    assert scan(store)==0 # new episode, no old timeout reused

def test_failed_listing_never_expires_observations(tmp_path):
    store=StateStore(str(tmp_path/'state.db'))
    async def listing(*args):return [pr()]
    github=SimpleNamespace(list_open_prs=listing)
    asyncio.run(monitor_timeouts(store,github,'owner/repo'))
    async def broken(*args):raise RuntimeError('network')
    github.list_open_prs=broken
    with pytest.raises(RuntimeError):asyncio.run(monitor_timeouts(store,github,'owner/repo'))
    with store.conn() as db: assert db.execute('SELECT active FROM timeout_observations').fetchone()[0]==1

def test_execution_lease_matches_reclaim_threshold_but_planner_lease_is_short(tmp_path):
    from orchestrator.recovery_policy import RUNNING_RECLAIM
    store=StateStore(str(tmp_path/'db'))
    store.enqueue('task','test',{})
    event=store.claim_next()
    expiry=datetime.fromisoformat(event['lease_expires_at']) if 'lease_expires_at' in event else datetime.fromisoformat(store.get('task')['lease_expires_at'])
    assert RUNNING_RECLAIM-5 < (expiry-datetime.now(timezone.utc)).total_seconds() <= RUNNING_RECLAIM
    store.observe_issue('owner/repo',80,'g','awaiting_planner',{})
    row=store.claim_issue('owner/repo',80,'g','worker','planner-token')
    assert 175 < (datetime.fromisoformat(row['expires_at'])-datetime.now(timezone.utc)).total_seconds() <= 3600
