"""Resolve abandoned confirmations from live evidence, never republish a plan."""
import hashlib
import json
import logging
from fastapi import HTTPException

from .planning_publication import verify_publication
from .issue_intake import references
from .state_store import now


async def recover_publications(store, github, repository):
    with store.conn() as db:
        rows=[dict(row) for row in db.execute(
            "SELECT * FROM planning_publications WHERE repository=? AND status='prepared'",(repository,))]
    if not rows:
        return 0
    prs=await github.list_open_prs(repository)
    recovered=0
    for row in rows:
        reason='PUBLICATION_NOT_OBSERVED';status='waiting';number=None
        try:
            with store.conn() as db:
                lease=db.execute('SELECT status,expires_at FROM issue_intake WHERE repository=? AND issue_number=?',
                    (repository,row['issue_number'])).fetchone()
            if lease and lease['status']=='leased' and lease['expires_at']>now():
                continue
            associated=[p for p in prs if row['issue_number'] in set.union(*references(p,repository))]
            if len(associated)>1:
                reason='PUBLICATION_ASSOCIATION_AMBIGUOUS'
            elif len(associated)==1:
                number=associated[0]['number']
                await verify_publication(store,github,row,number,allow_descendant=True)
                status='applied';reason='VERIFIED_ABANDONED_CONFIRMATION';recovered+=1
        except HTTPException as exc:
            # Validator reasons are enumerated and contain no response bodies.
            reason=str(exc.detail)
        except Exception as exc:
            reason='PUBLICATION_EVIDENCE_UNAVAILABLE'
            logging.getLogger(__name__).warning('planning recovery deferred: %s',type(exc).__name__)
        store.record_recovery_audit('planning:'+row['publication_id'],dict(
            rule_id='PLANNING_PUBLICATION_RECOVERY',repository=repository,pr_number=number,
            issue_number=row['issue_number'],source_sha=json.loads(row['intent_json'])['head_sha'],
            lease_id='publication-reconciler',status=status,reason=reason,created_at=now(),
            action_type='confirm_observation',evidence_generation=hashlib.sha256(
                json.dumps([row['publication_id'],number,reason]).encode()).hexdigest()))
    return recovered
