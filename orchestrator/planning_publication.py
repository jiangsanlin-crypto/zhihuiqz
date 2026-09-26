"""Reserve and verify planning publication; never creates branches or PRs."""
import hashlib
import json

from fastapi import HTTPException
from pydantic import Field

from .issue_intake import IntakeClaim, generation, references, scan_issues
from .state_store import now
from .task_router import TASK_MARKER, label_names


class PreparePlan(IntakeClaim):
    head_ref: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9/_-]{0,199}$')
    head_sha: str = Field(pattern=r'^[0-9a-f]{40}$')
    base_ref: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9/_-]{0,199}$')
    body_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class ConfirmPlan(IntakeClaim):
    publication_id: str = Field(pattern=r'^[0-9a-f]{64}$')
    pr_number: int = Field(gt=0)


def install_publication_routes(router, store, github, repository):
    with store.conn() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS planning_publications(
            repository TEXT, issue_number INTEGER, publication_id TEXT UNIQUE,
            generation TEXT, owner_hash TEXT, intent_json TEXT,
            status TEXT, pr_number INTEGER, created_at TEXT, updated_at TEXT,
            PRIMARY KEY(repository,issue_number))''')

    def owner(value):
        return hashlib.sha256(json.dumps([value.worker_id,value.lease_id]).encode()).hexdigest()

    @router.post('/prepare-publication')
    async def prepare(value: PreparePlan):
        repo=repository()
        await scan_issues(store,github,repo)
        default=await github.get_default_branch(repo)
        if value.head_ref in {'main',default,value.base_ref}:
            raise HTTPException(409,'PROTECTED_PUBLICATION_BRANCH')
        intent=value.model_dump(exclude={'worker_id','lease_id'})
        encoded=json.dumps(intent,sort_keys=True)
        identity=hashlib.sha256(json.dumps([repo,encoded,owner(value)]).encode()).hexdigest()
        with store.lock, store.conn() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT * FROM planning_publications WHERE repository=? AND issue_number=?',
                                (repo,value.issue_number)).fetchone()
            row=db.execute('SELECT * FROM issue_intake WHERE repository=? AND issue_number=?',
                           (repo,value.issue_number)).fetchone()
            if (not row or row['generation']!=value.generation or row['status']!='leased'
                or row['worker_id']!=value.worker_id or row['lease_id']!=value.lease_id or row['expires_at']<=now()):
                raise HTTPException(409,'PLANNER_LEASE_LOST')
            if existing:
                if existing['publication_id']!=identity:
                    raise HTTPException(409,'PUBLICATION_ALREADY_RESERVED')
                return {'publication_id':identity,'status':existing['status']}
            for reserved in db.execute('SELECT issue_number,intent_json FROM planning_publications WHERE repository=?',(repo,)):
                if reserved['issue_number']!=value.issue_number and json.loads(reserved['intent_json'])['head_ref']==value.head_ref:
                    raise HTTPException(409,'PUBLICATION_BRANCH_ALREADY_RESERVED')
            db.execute('INSERT INTO planning_publications VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (repo,value.issue_number,identity,value.generation,owner(value),encoded,'prepared',None,now(),now()))
        return {'publication_id':identity,'status':'prepared'}

    @router.post('/confirm-publication')
    async def confirm(value: ConfirmPlan):
        repo=repository()
        with store.conn() as db:
            row=db.execute('SELECT * FROM planning_publications WHERE repository=? AND issue_number=?',
                           (repo,value.issue_number)).fetchone()
        if (not row or row['publication_id']!=value.publication_id or row['owner_hash']!=owner(value)
            or row['generation']!=value.generation or (row['pr_number'] and row['pr_number']!=value.pr_number)):
            raise HTTPException(409,'PUBLICATION_IDENTITY_CHANGED')
        intent=json.loads(row['intent_json'])
        issues=await github.list_open_issues(repo)
        issue=next((x for x in issues if x['number']==value.issue_number),None)
        if not issue or generation(issue)!=value.generation:
            raise HTTPException(409,'ISSUE_CHANGED')
        prs=await github.list_open_prs(repo)
        associated=[p for p in prs if value.issue_number in set.union(*references(p,repo))]
        if len(associated)!=1 or associated[0]['number']!=value.pr_number:
            raise HTTPException(409,'PUBLICATION_ASSOCIATION_AMBIGUOUS')
        pr=await github.get_pr_snapshot(repo,value.pr_number)
        head,base=pr.get('head') or {},pr.get('base') or {}
        default=await github.get_default_branch(repo)
        body=pr.get('body') or ''
        if (pr.get('state')!='open' or pr.get('merged_at')
            or head.get('ref')!=intent['head_ref'] or head.get('sha')!=intent['head_sha']
            or (head.get('repo') or {}).get('full_name')!=repo
            or base.get('ref')!=intent['base_ref'] or head.get('ref') in {'main',default,base.get('ref')}
            or set(TASK_MARKER.findall(body))!={f'GH-ISSUE-{value.issue_number}'}
            or hashlib.sha256(body.encode()).hexdigest()!=intent['body_sha256']
            or any(x.startswith('approval:') or x=='status:review' for x in label_names(pr.get('labels')))):
            raise HTTPException(409,'PUBLICATION_CONTENT_CHANGED')
        # Re-read issue generation after the PR reads. Confirmation observes
        # already-published work, never grants an expired planner another write.
        current=next((x for x in await github.list_open_issues(repo) if x['number']==value.issue_number),None)
        if not current or generation(current)!=value.generation:
            raise HTTPException(409,'ISSUE_CHANGED')
        with store.lock, store.conn() as db:
            db.execute('BEGIN IMMEDIATE')
            lease=db.execute('SELECT * FROM issue_intake WHERE repository=? AND issue_number=?',
                             (repo,value.issue_number)).fetchone()
            if (not lease or lease['generation']!=value.generation
                or (lease['status']=='leased' and lease['lease_id']!=value.lease_id)):
                raise HTTPException(409,'PLANNER_OWNERSHIP_CHANGED')
            db.execute("UPDATE planning_publications SET status='applied',pr_number=?,updated_at=? WHERE publication_id=?",
                       (value.pr_number,now(),value.publication_id))
            payload=json.loads(lease['payload_json']);payload['linked_prs']=[value.pr_number]
            db.execute("""UPDATE issue_intake SET status='linked',payload_json=?,worker_id=NULL,lease_id=NULL,
                expires_at=NULL,updated_at=? WHERE repository=? AND issue_number=?""",
                (json.dumps(payload),now(),repo,value.issue_number))
        return {'publication_id':value.publication_id,'status':'applied','pr_number':value.pr_number}
