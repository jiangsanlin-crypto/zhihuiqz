"""Shared leased label writer for participating controller paths."""
import json
import hashlib
from .state_store import now
from .task_router import label_names


def canonical(labels):
    states={x for x in labels if x.startswith('status:')}
    agents={x for x in labels if x.startswith('agent:')}
    phases={x for x in labels if x.startswith('phase:')}
    approvals={x for x in labels if x.startswith('approval:')}
    if states=={'status:review'}:
        return (not agents and not phases and bool(approvals)
                and not any(x.startswith(('blocker:', 'recovery:', 'watchdog:')) for x in labels))
    return (len(states)==len(agents)==len(phases)==1 and not approvals
            and states <= {'status:todo','status:running','status:blocked'})


async def write_labels(store, github, binding, delivery, lease, before, after):
    before,after=set(before),set(after)
    unrelated = {x for x in before if not x.startswith(
        ('agent:', 'phase:', 'status:', 'approval:', 'blocker:', 'recovery:', 'watchdog:'))}
    if not unrelated <= after:
        raise RuntimeError('UNRELATED_LABEL_REMOVAL')
    if not canonical(after):
        raise RuntimeError('STATE_RECONCILIATION_AMBIGUOUS')
    if any(x.startswith('approval:') or x=='status:review' for x in before):
        raise RuntimeError('HUMAN_WAIT_PROTECTED')
    projection=json.dumps([binding['repository'],binding['pr_number'],'state-projection'])
    if not store.claim_operation(projection,delivery,lease):
        raise RuntimeError('ANOTHER_WORKER_OWNS_PROJECTION')
    async def verify(expected):
        pr=await github.get_pr_snapshot(binding['repository'],binding['pr_number'])
        head,base=pr.get('head') or {},pr.get('base') or {}
        if (pr.get('state')!='open' or pr.get('merged_at') or head.get('sha')!=binding['source_sha']
            or head.get('ref')!=binding['head_ref']
            or (head.get('repo') or {}).get('full_name')!=binding['repository']
            or head.get('ref') in {'main',base.get('ref'),(head.get('repo') or {}).get('default_branch')}
            or (binding.get('base_ref') and base.get('ref')!=binding['base_ref'])):
            raise RuntimeError('PR_BRANCH_IDENTITY_CHANGED')
        labels=set(label_names(pr.get('labels')))
        if labels!=expected:
            raise RuntimeError('STATE_CHANGED')
        store.assert_lease(delivery,lease)
        store.assert_operation(projection,delivery,lease)
        if binding.get('operation_key'):
            store.assert_operation(binding['operation_key'],delivery,lease)
    await verify(before)
    audit=dict(rule_id='SHARED_STATE_WRITER',repository=binding['repository'],
        pr_number=binding['pr_number'],source_sha=binding['source_sha'],
        task_id=binding.get('task_id'),phase=binding.get('phase'),lease_id=lease,
        action_type='project',status='planned',created_at=now(),
        labels_before=sorted(before),labels_after=sorted(after),
        evidence_generation=hashlib.sha256(json.dumps([binding,sorted(before),sorted(after)],sort_keys=True).encode()).hexdigest())
    store.record_recovery_audit(delivery,audit)
    if before!=after:
        await github.set_labels(binding['repository'],binding['pr_number'],sorted(after))
    await verify(after)
    audit['status']='applied'
    store.record_recovery_audit(delivery,audit)
