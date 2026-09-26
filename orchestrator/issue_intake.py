"""Durable issue discovery for an authenticated planning host; no GitHub writes."""
import hashlib
import json
import re

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .security import verify_bearer
from .task_router import TASK_MARKER, label_names
from .state_store import now

ROOT_MARKERS = ("<!-- agent-root-task:v1 -->", "<!-- synthetic-e2e:true -->")


def is_root_task(issue) -> bool:
    body = str(issue.get("body") or "")
    return any(marker in body for marker in ROOT_MARKERS)


def generation(issue):
    data = [issue.get('title'), issue.get('body'), issue.get('state'),
            sorted(label_names(issue.get('labels'))), (issue.get('user') or {}).get('login')]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def references(pr, repository):
    body = pr.get('body') or ''
    marked = {int(x.removeprefix('GH-ISSUE-')) for x in TASK_MARKER.findall(body)
              if re.fullmatch(r'GH-ISSUE-\d+', x)}
    prefix = rf'(?:https://github\.com/{re.escape(repository)}/issues/|{re.escape(repository)}#|#)'
    closing = {int(x) for x in re.findall(r'(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+' + prefix + r'(\d+)\b', body)}
    weak = {int(x) for x in re.findall(r'(?<![\w/])#(\d+)\b', body)}
    return marked | closing, weak


async def scan_issues(store, github, repository):
    issues = await github.list_open_issues(repository)
    prs = await github.list_open_prs(repository)
    associations = [(pr, *references(pr, repository)) for pr in prs]
    seen = set()
    for issue in issues:
        number = issue['number']
        seen.add(number)
        strong = [pr for pr, refs, _ in associations if refs == {number}]
        ambiguous = [pr for pr, refs, weak in associations if number in (refs | weak) and pr not in strong]
        status = 'awaiting_planner'
        if (issue.get('user') or {}).get('login') != repository.split('/')[0]:
            status = 'needs_triage'
        if not str(issue.get('body') or '').strip():
            status = 'needs_task_spec'
        elif not is_root_task(issue):
            status = 'not_agent_root'
        if any(x.startswith(('approval:', 'blocker:')) or x in {'status:blocked', 'status:review', 'status:done'}
               for x in label_names(issue.get('labels'))):
            status = 'human_wait'
        if len(strong) == 1 and not ambiguous:
            status = 'linked'
        elif strong or ambiguous:
            status = 'needs_link_resolution'
        store.observe_issue(repository, number, generation(issue), status,
            {'task_id': f'GH-ISSUE-{number}', 'title': issue.get('title'),
             'issue_url': issue.get('html_url'), 'linked_prs': [pr['number'] for pr in strong],
             'ambiguous_prs': [pr['number'] for pr in ambiguous]})
    # Only close absent rows after both complete paginated reads succeeded.
    for old in store.intake_items(repository):
        if old['issue_number'] not in seen and old['status'] != 'closed':
            store.observe_issue(repository, old['issue_number'], old['generation'], 'closed',
                                json.loads(old['payload_json']))
    return len(issues)


class IntakeClaim(BaseModel):
    model_config = {'extra': 'forbid'}
    issue_number: int = Field(gt=0)
    generation: str = Field(pattern=r'^[0-9a-f]{64}$')
    worker_id: str = Field(pattern=r'^[A-Za-z0-9._:-]{1,150}$')
    lease_id: str = Field(pattern=r'^[A-Za-z0-9._:-]{16,150}$')


def create_intake_router(store, github, settings):
    async def authenticated(authorization: str | None = Header(None)):
        if not verify_bearer(settings.orchestrator_token, authorization):
            raise HTTPException(401, 'invalid intake authentication')
    router = APIRouter(prefix='/intake', dependencies=[Depends(authenticated)])

    def repository():
        if not settings.github_repository:
            raise HTTPException(503, 'REPOSITORY_NOT_CONFIGURED')
        return settings.github_repository

    @router.get('/issues')
    async def issues():
        # Lease tokens are never returned by a queue listing. An uncertain
        # publication must be confirmed, never advertised as fresh planning.
        with store.conn() as db:
            reserved={row[0] for row in db.execute(
                "SELECT issue_number FROM planning_publications WHERE repository=? AND status='prepared'",
                (repository(),))}
        return {'issues': [{**{key: row[key] for key in
            ('issue_number', 'generation', 'status', 'payload_json', 'updated_at')},
            'claimable': row['issue_number'] not in reserved and (row['status'] == 'awaiting_planner' or
                (row['status'] == 'leased' and row['expires_at'] <= now()))}
            for row in store.intake_items(repository())]}

    @router.post('/acquire')
    async def acquire(value: IntakeClaim):
        repo = repository()
        await scan_issues(store, github, repo)  # Fresh issue + PR deduplication before CAS.
        try:
            row = store.claim_issue(repo, value.issue_number, value.generation, value.worker_id, value.lease_id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {key: row[key] for key in ('issue_number', 'generation', 'lease_id', 'expires_at')}

    @router.post('/heartbeat')
    async def heartbeat(value: IntakeClaim):
        repo = repository()
        await scan_issues(store, github, repo)
        if not store.renew_issue(repo, value.issue_number, value.generation, value.worker_id, value.lease_id):
            raise HTTPException(409, 'PLANNER_LEASE_LOST')
        return {'renewed': True}

    from .planning_publication import install_publication_routes
    install_publication_routes(router, store, github, repository)
    return router
