import asyncio
import json
import pytest
from test_planning_publication import publication,publish
from test_issue_intake import intake
from orchestrator.planning_recovery import recover_publications


def recover(data):
    return asyncio.run(recover_publications(data[0][0],data[0][3],'owner/repo'))

def expire(data):
    with data[0][0].conn() as db:db.execute("UPDATE issue_intake SET expires_at='2000-01-01'")

def test_orphaned_published_plan_confirms_without_original_host(publication):
    publish(publication)
    assert recover(publication)==0 # active planner owns confirmation
    expire(publication)
    assert recover(publication)==1
    assert recover(publication)==0
    assert publication[0][0].intake_items('owner/repo')[0]['status']=='linked'

@pytest.mark.parametrize('change',['no_pr','duplicate','sha','issue','human','network'])
def test_uncertain_or_changed_publication_never_republishes(publication,change):
    publish(publication);expire(publication)
    data=publication[0]
    if change=='no_pr':data[2].clear()
    elif change=='duplicate':data[2].append(dict(data[2][0],number=84))
    elif change=='sha':data[2][0]['head']['sha']='b'*40
    elif change=='issue':data[1][0]['body']+=' changed'
    elif change=='human':data[2][0]['labels']=['status:review']
    else:
        async def broken(*args):raise RuntimeError('sensitive remote failure')
        data[3].get_pr_snapshot=broken
    assert recover(publication)==0
    with data[0].conn() as db:
        assert db.execute('SELECT status FROM planning_publications').fetchone()[0]=='prepared'
        audit=json.loads(db.execute('SELECT payload_json FROM recovery_audit').fetchone()[0])
        assert audit['status']=='waiting'
        assert 'sensitive' not in str(audit)
    # Same observation is audited once across repeated scans.
    assert recover(publication)==0
    with data[0].conn() as db:assert db.execute('SELECT COUNT(*) FROM recovery_audit').fetchone()[0]==1
