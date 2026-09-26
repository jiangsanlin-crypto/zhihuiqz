import copy
import pytest
from test_planning_publication import publication,publish
from test_issue_intake import intake,AUTH

@pytest.fixture
def resumable(publication):
    receipt=publish(publication);publication[0][2].clear()
    async def history(*args):return []
    async def branch(*args):return 'a'*40
    publication[0][3].list_branch_prs=history;publication[0][3].get_branch_sha=branch
    with publication[0][0].conn() as db:db.execute("UPDATE issue_intake SET expires_at='2000-01-01'")
    request=dict(receipt,worker_id='replacement',lease_id='new-planner-lease-0001');request.pop('pr_number')
    return publication,receipt,request

def test_takeover_preserves_intent_and_fences_original_planner(resumable):
    data,old,request=resumable;client=data[0][-1]
    result=client.post('/intake/resume-publication',json=request,headers=AUTH)
    assert result.status_code==200,result.text
    assert result.json()['intent']['head_sha']=='a'*40
    assert result.json()['new_branch_allowed'] is False
    # Same owner can safely recover the response without reserving another plan.
    assert client.post('/intake/resume-publication',json=request,headers=AUTH).status_code==200
    assert client.post('/intake/resume-publication',json=dict(request,worker_id='rival',lease_id='rival-lease-00001'),headers=AUTH).status_code==409
    data[0][2].append(dict(number=83,state='open',body=data[3],labels=[],base={'ref':'main'},
        head={'ref':'plans/issue-80','sha':'a'*40,'repo':{'full_name':'owner/repo'}}))
    assert client.post('/intake/confirm-publication',json=old,headers=AUTH).status_code==409
    assert client.post('/intake/confirm-publication',json=dict(request,pr_number=83),headers=AUTH).status_code==200

@pytest.mark.parametrize('change',['closed_pr','head','issue','live_owner','default_branch','network'])
def test_conflicting_reservations_never_rebuild_or_overwrite(resumable,change):
    data,old,request=resumable;github=data[0][3]
    if change=='closed_pr':
        async def history(*args):return [{'number':81,'state':'closed'}]
        github.list_branch_prs=history
    elif change=='head':
        async def branch(*args):return 'b'*40
        github.get_branch_sha=branch
    elif change=='issue':data[0][1][0]['body']+=' changed'
    elif change=='live_owner':
        with data[0][0].conn() as db:db.execute("UPDATE issue_intake SET expires_at='2999-01-01'")
    elif change=='default_branch':
        async def default(*args):return 'plans/issue-80'
        github.get_default_branch=default
    else:
        async def history(*args):raise RuntimeError('network')
        github.list_branch_prs=history
    if change=='network':
        with pytest.raises(RuntimeError):data[0][-1].post('/intake/resume-publication',json=request,headers=AUTH)
    else:assert data[0][-1].post('/intake/resume-publication',json=request,headers=AUTH).status_code==409
    with data[0][0].conn() as db:
        assert db.execute('SELECT status FROM planning_publications').fetchone()[0]=='prepared'
        assert db.execute('SELECT COUNT(*) FROM planning_publications').fetchone()[0]==1


def test_absent_branch_allows_only_declared_ref_and_commit(resumable):
    data,_,request=resumable
    async def absent(*args):return None
    data[0][3].get_branch_sha=absent
    result=data[0][-1].post('/intake/resume-publication',json=request,headers=AUTH)
    assert result.status_code==200
    assert result.json()['declared_branch_creation_allowed'] is True
    assert result.json()['intent']['head_ref']=='plans/issue-80'
    assert result.json()['intent']['head_sha']=='a'*40
    assert result.json()['new_branch_allowed'] is False
    assert result.json()['force_push_allowed'] is False


def test_issue_edit_during_takeover_is_fenced(resumable):
    data,_,request=resumable
    async def history(*args):
        data[0][1][0]['body']+=' concurrent edit'
        return []
    data[0][3].list_branch_prs=history
    assert data[0][-1].post('/intake/resume-publication',json=request,headers=AUTH).status_code==409
