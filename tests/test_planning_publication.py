import copy
import hashlib
import pytest
from test_issue_intake import intake, claim, AUTH

@pytest.fixture
def publication(intake):
    store,issues,prs,github,client=intake
    async def default(*args): return 'main'
    async def snapshot(*args): return copy.deepcopy(prs[0])
    github.get_default_branch=default;github.get_pr_snapshot=snapshot
    value=claim(intake)
    assert client.post('/intake/acquire',json=value,headers=AUTH).status_code==200
    body='<!-- agent-task-id:GH-ISSUE-80 -->\nCloses #80\nPlan: add queue discovery.'
    prepare=dict(value,head_ref='plans/issue-80',head_sha='a'*40,base_ref='main',body_sha256=hashlib.sha256(body.encode()).hexdigest())
    return intake,value,prepare,body

def publish(data):
    intake,value,prepare,body=data
    result=intake[-1].post('/intake/prepare-publication',json=prepare,headers=AUTH)
    assert result.status_code==200,result.text
    intake[2].append(dict(number=83,state='open',body=body,labels=[],base={'ref':'main'},
        head={'sha':'a'*40,'ref':'plans/issue-80','repo':{'full_name':'owner/repo'}}))
    return dict(value,publication_id=result.json()['publication_id'],pr_number=83)

def test_confirm_lost_response_is_idempotent_and_preserves_association(publication):
    payload=publish(publication);client=publication[0][-1]
    assert client.post('/intake/confirm-publication',json=payload,headers=AUTH).status_code==200
    assert client.post('/intake/confirm-publication',json=payload,headers=AUTH).status_code==200
    assert publication[0][0].intake_items('owner/repo')[0]['status']=='linked'

@pytest.mark.parametrize('change',['issue','sha','body','fork','base','human','duplicate','token'])
def test_confirmation_rejects_changed_evidence(publication,change):
    payload=publish(publication);intake=publication[0];pr=intake[2][0]
    if change=='issue': intake[1][0]['body']+=' changed'
    elif change=='sha': pr['head']['sha']='b'*40
    elif change=='body': pr['body']+=' modified'
    elif change=='fork': pr['head']['repo']['full_name']='other/repo'
    elif change=='base': pr['base']['ref']='release'
    elif change=='human': pr['labels']=['status:review']
    elif change=='duplicate': intake[2].append(dict(pr,number=84))
    else: payload['lease_id']='different-token-0001'
    assert intake[-1].post('/intake/confirm-publication',json=payload,headers=AUTH).status_code==409

def test_expired_reservation_cannot_be_replaced_but_can_confirm_observed_publication(publication):
    payload=publish(publication);intake=publication[0];pr=intake[2].pop()
    with intake[0].conn() as db: db.execute("UPDATE issue_intake SET expires_at='2000-01-01'")
    assert intake[-1].post('/intake/acquire',json=dict(publication[1],lease_id='replacement-lease-01'),headers=AUTH).status_code==409
    assert intake[-1].post('/intake/prepare-publication',json=publication[2],headers=AUTH).status_code==409
    intake[2].append(pr)
    assert intake[-1].post('/intake/confirm-publication',json=payload,headers=AUTH).status_code==200

def test_protected_branch_and_unauthenticated_publication_rejected(publication):
    client=publication[0][-1]
    assert client.post('/intake/prepare-publication',json=publication[2]).status_code==401
    assert client.post('/intake/prepare-publication',json=dict(publication[2],head_ref='main'),headers=AUTH).status_code==409

def test_uncertain_publication_is_not_advertised_as_new_work(publication):
    publish(publication)
    publication[0][2].clear()
    with publication[0][0].conn() as db:db.execute("UPDATE issue_intake SET expires_at='2000-01-01'")
    row=publication[0][-1].get('/intake/issues',headers=AUTH).json()['issues'][0]
    assert row['claimable'] is False
