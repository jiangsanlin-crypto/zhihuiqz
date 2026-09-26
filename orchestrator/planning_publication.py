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


class ResumePlan(IntakeClaim):
    publication_id: str = Field(pattern=r'^[0-9a-f]{64}$')


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

    @router.get('/publications')
    async def publications():
        with store.conn() as db:
            rows=db.execute("SELECT publication_id,intent_json,status,pr_number FROM planning_publications WHERE repository=?",(repository(),)).fetchall()
        return {'publications':[dict(publication_id=row['publication_id'],intent=json.loads(row['intent_json']),
                                    status=row['status'],pr_number=row['pr_number']) for row in rows]}

    @router.post('/resume-publication')
    async def resume(value: ResumePlan):
        repo=repository()
        with store.conn() as db:
            initial=db.execute('SELECT * FROM planning_publications WHERE repository=? AND issue_number=?',
                (repo,value.issue_number)).fetchone()
        if not initial or initial['publication_id']!=value.publication_id or initial['status']!='prepared':
            raise HTTPException(409,'PUBLICATION_NOT_PENDING')
        if initial['generation']!=value.generation:raise HTTPException(409,'ISSUE_CHANGED')
        intent=json.loads(initial['intent_json'])
        await scan_issues(store,github,repo)
        # Include closed PRs and unmatched bodies. A closed publication is an
        # owner decision, not proof that a second PR should be created.
        if await github.list_branch_prs(repo,intent['head_ref']):
            raise HTTPException(409,'PUBLICATION_HISTORY_REQUIRES_RECONCILIATION')
        actual=await github.get_branch_sha(repo,intent['head_ref'])
        if actual is not None and actual!=intent['head_sha']:
            raise HTTPException(409,'PUBLICATION_BRANCH_CONFLICT')
        default=await github.get_default_branch(repo)
        if intent['head_ref'] in {'main',default,intent['base_ref']}:
            raise HTTPException(409,'PROTECTED_PUBLICATION_BRANCH')
        latest=next((item for item in await github.list_open_issues(repo) if item['number']==value.issue_number),None)
        if not latest or generation(latest)!=value.generation:
            raise HTTPException(409,'ISSUE_CHANGED')
        with store.lock,store.conn() as db:
            db.execute('BEGIN IMMEDIATE')
            live=db.execute('SELECT * FROM planning_publications WHERE publication_id=?',(value.publication_id,)).fetchone()
            lease=db.execute('SELECT * FROM issue_intake WHERE repository=? AND issue_number=?',(repo,value.issue_number)).fetchone()
            if not live or live['status']!='prepared' or live['owner_hash']!=initial['owner_hash']:
                raise HTTPException(409,'PUBLICATION_OWNERSHIP_CHANGED')
            if not lease or lease['generation']!=value.generation or lease['status'] not in {'awaiting_planner','leased'}:
                raise HTTPException(409,'ISSUE_NOT_READY')
            if lease['status']=='leased' and lease['expires_at']>now():
                if lease['worker_id']!=value.worker_id or lease['lease_id']!=value.lease_id:
                    raise HTTPException(409,'ANOTHER_PLANNER_OWNS_LEASE')
            elif lease['lease_id']==value.lease_id:
                raise HTTPException(409,'PLANNER_LEASE_EXPIRED')
            from datetime import datetime,timedelta,timezone
            from .state_store import PLANNER_LEASE_SECONDS
            expiry=(datetime.now(timezone.utc)+timedelta(seconds=PLANNER_LEASE_SECONDS)).isoformat()
            db.execute("UPDATE planning_publications SET owner_hash=?,updated_at=? WHERE publication_id=?",
                (owner(value),now(),value.publication_id))
            db.execute("""UPDATE issue_intake SET status='leased',worker_id=?,lease_id=?,expires_at=?,updated_at=?
                WHERE repository=? AND issue_number=?""",(value.worker_id,value.lease_id,expiry,now(),repo,value.issue_number))
        store.record_recovery_audit('planning:'+value.publication_id,dict(rule_id='PLANNING_RESUME',
            repository=repo,issue_number=value.issue_number,lease_id=value.lease_id,status='applied',
            action_type='resume_same_intent',reason='same generation and branch; no historical publication',
            evidence_generation=value.publication_id,created_at=now()))
        return {'publication_id':value.publication_id,'status':'prepared','intent':intent,
                'expires_at':expiry,'new_branch_allowed':False,'force_push_allowed':False,
                'declared_branch_creation_allowed':actual is None}

    @router.post('/confirm-publication')
    async def confirm(value: ConfirmPlan):
        repo=repository()
        with store.conn() as db:
            row=db.execute('SELECT * FROM planning_publications WHERE repository=? AND issue_number=?',
                           (repo,value.issue_number)).fetchone()
        if (not row or row['publication_id']!=value.publication_id or row['owner_hash']!=owner(value)
            or row['generation']!=value.generation or (row['pr_number'] and row['pr_number']!=value.pr_number)):
            raise HTTPException(409,'PUBLICATION_IDENTITY_CHANGED')
        return await verify_publication(store, github, dict(row), value.pr_number)


async def verify_publication(store, github, row, pr_number, *, allow_descendant=False):
    """Observe immutable publication evidence; performs no GitHub mutation."""
    repo=row['repository']
    intent=json.loads(row['intent_json'])
    issues=await github.list_open_issues(repo)
    issue=next((x for x in issues if x['number']==row['issue_number']),None)
    if not issue or generation(issue)!=row['generation']:
        raise HTTPException(409,'ISSUE_CHANGED')
    prs=await github.list_open_prs(repo)
    associated=[p for p in prs if row['issue_number'] in set.union(*references(p,repo))]
    if len(associated)!=1 or associated[0]['number']!=pr_number:
        raise HTTPException(409,'PUBLICATION_ASSOCIATION_AMBIGUOUS')
    pr=await github.get_pr_snapshot(repo,pr_number)
    head,base=pr.get('head') or {},pr.get('base') or {}
    default=await github.get_default_branch(repo)
    body=pr.get('body') or ''
    head_matches=head.get('sha')==intent['head_sha']
    if (not head_matches and allow_descendant
        and (head.get('repo') or {}).get('full_name')==repo):
        ancestry=await github.compare_commits(repo,intent['head_sha'],head.get('sha'))
        head_matches=(ancestry.get('status')=='ahead'
            and (ancestry.get('base_commit') or {}).get('sha')==intent['head_sha']
            and (ancestry.get('merge_base_commit') or {}).get('sha')==intent['head_sha'])
    if (pr.get('state')!='open' or pr.get('merged_at')
        or head.get('ref')!=intent['head_ref'] or not head_matches
        or (head.get('repo') or {}).get('full_name')!=repo
        or base.get('ref')!=intent['base_ref'] or head.get('ref') in {'main',default,base.get('ref')}
        or set(TASK_MARKER.findall(body))!={f"GH-ISSUE-{row['issue_number']}"}
        or hashlib.sha256(body.encode()).hexdigest()!=intent['body_sha256']
        or any(x.startswith('approval:') or x=='status:review' for x in label_names(pr.get('labels')))):
        raise HTTPException(409,'PUBLICATION_CONTENT_CHANGED')
    # Publication confirmation is the only authority that activates a newly
    # planned PR. Labels are a projection of the verified immutable publication,
    # never a planner-authored side effect.
    target_workflow = {"agent:workbuddy", "phase:prototype", "status:todo"}
    before = set(label_names(pr.get("labels")))
    workflow = {
        value for value in before
        if value.startswith(("agent:", "phase:", "status:", "approval:"))
    }
    if workflow not in (set(), target_workflow):
        raise HTTPException(409, "PUBLICATION_STATE_CHANGED")
    after = {
        value for value in before
        if not value.startswith(("agent:", "phase:", "status:", "approval:",
                                 "blocker:", "recovery:", "watchdog:"))
    } | target_workflow
    if before != after:
        live = await github.get_pr_snapshot(repo, pr_number)
        if ((live.get("head") or {}).get("sha") != head.get("sha")
            or set(label_names(live.get("labels"))) != before):
            raise HTTPException(409, "PUBLICATION_STATE_CHANGED")
        await github.set_labels(repo, pr_number, sorted(after))
        projected = await github.get_pr_snapshot(repo, pr_number)
        if ((projected.get("head") or {}).get("sha") != head.get("sha")
            or set(label_names(projected.get("labels"))) != after):
            raise HTTPException(409, "PUBLICATION_PROJECTION_UNVERIFIED")
        store.record_recovery_audit("planning:" + row["publication_id"], dict(
            rule_id="PLANNING_PUBLICATION_ACTIVATE",
            repository=repo,
            pr_number=pr_number,
            issue_number=row["issue_number"],
            source_sha=head.get("sha"),
            lease_id="planning-publication",
            status="applied",
            action_type="project",
            reason="verified publication activated through shared controller",
            labels_before=sorted(before),
            labels_after=sorted(after),
            evidence_generation=row["publication_id"],
            created_at=now(),
        ))

    # Re-read issue generation after the PR reads. Confirmation observes
    # already-published work, never grants an expired planner another write.
    current=next((x for x in await github.list_open_issues(repo) if x['number']==row['issue_number']),None)
    if not current or generation(current)!=row['generation']:
        raise HTTPException(409,'ISSUE_CHANGED')
    with store.lock, store.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        live=db.execute('SELECT * FROM planning_publications WHERE publication_id=?',(row['publication_id'],)).fetchone()
        if not live or live['generation']!=row['generation'] or (live['pr_number'] and live['pr_number']!=pr_number):
            raise HTTPException(409,'PUBLICATION_IDENTITY_CHANGED')
        lease=db.execute('SELECT * FROM issue_intake WHERE repository=? AND issue_number=?',
                         (repo,row['issue_number'])).fetchone()
        if (not lease or lease['generation']!=row['generation']
            or (lease['status']=='leased' and hashlib.sha256(json.dumps([lease['worker_id'],lease['lease_id']]).encode()).hexdigest()!=row['owner_hash'])):
            raise HTTPException(409,'PLANNER_OWNERSHIP_CHANGED')
        db.execute("UPDATE planning_publications SET status='applied',pr_number=?,updated_at=? WHERE publication_id=?",
                   (pr_number,now(),row['publication_id']))
        payload=json.loads(lease['payload_json']);payload['linked_prs']=[pr_number]
        db.execute("""UPDATE issue_intake SET status='linked',payload_json=?,worker_id=NULL,lease_id=NULL,
            expires_at=NULL,updated_at=? WHERE repository=? AND issue_number=?""",
            (json.dumps(payload),now(),repo,row['issue_number']))
    return {'publication_id':row['publication_id'],'status':'applied','pr_number':pr_number}
