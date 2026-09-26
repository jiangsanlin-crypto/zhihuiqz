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

@pytest.mark.parametrize('ancestor',[True,False])
def test_legitimate_descendant_resolves_association_without_advancing_old_evidence(publication,ancestor):
    publish(publication);expire(publication)
    pr=publication[0][2][0];pr['head']['sha']='b'*40
    before=pr['labels'][:]
    async def compare(*args):
        return dict(status='ahead' if ancestor else 'diverged',base_commit={'sha':'a'*40},
                    merge_base_commit={'sha':'a'*40 if ancestor else 'c'*40})
    publication[0][3].compare_commits=compare
    assert recover(publication)==int(ancestor)
    assert pr['labels']==before and pr['head']['sha']=='b'*40
    with publication[0][0].conn() as db:
        row=db.execute('SELECT * FROM planning_publications').fetchone()
        assert row['status']==('applied' if ancestor else 'prepared')
        assert json.loads(row['intent_json'])['head_sha']=='a'*40
