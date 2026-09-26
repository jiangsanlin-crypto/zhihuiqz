"""Rebind a lease only to a commit declared before its branch publication.

No GitHub writes or evidence reuse. Old-SHA CI/review never authorizes new HEAD.
"""
import hashlib
import json

from .handoff_gate import HandoffGateError
from .state_store import now
from .task_router import TASK_MARKER, label_names


def publication_audit(binding, lease, intent, status):
    return dict(rule_id='DECLARED_HEAD_PUBLICATION', lease_id=lease,
        repository=binding['repository'], pr_number=binding['pr_number'],
        worker_id=binding['worker_id'], phase=binding['phase'],
        source_sha=intent['from_sha'], target_sha=intent['to_sha'],
        action_type='invalidate_old_sha', status=status, created_at=now(),
        reason='predeclared direct-child commit; new SHA requires fresh phase evidence',
        evidence_generation=hashlib.sha256(json.dumps(intent, sort_keys=True).encode()).hexdigest())


async def refresh_declared_head(store, github, row, binding):
    checkpoint = json.loads(row.get('checkpoint_json') or '{}')
    intent = checkpoint.get('head_publication')
    if not intent:
        return row, binding
    if intent['status'] == 'applied':
        store.record_recovery_audit(row['delivery_id'], publication_audit(binding, row['lease_id'], intent, 'applied'))
        return row, binding
    pr = await github.get_pr_snapshot(binding['repository'], binding['pr_number'])
    head, base = pr.get('head') or {}, pr.get('base') or {}
    if head.get('sha') == binding['source_sha']:
        return row, binding
    labels = set(label_names(pr.get('labels')))
    route = {x for x in labels if x.startswith(('agent:', 'phase:', 'status:', 'approval:'))}
    if (pr.get('state') != 'open' or pr.get('merged_at')
        or head.get('sha') != intent['to_sha'] or binding['source_sha'] != intent['from_sha']
        or head.get('ref') != binding['head_ref'] or base.get('ref') != intent['base_ref']
        or (head.get('repo') or {}).get('full_name') != binding['repository']
        or head.get('ref') in {'main', base.get('ref'), (head.get('repo') or {}).get('default_branch')}
        or set(TASK_MARKER.findall(pr.get('body') or '')) != {binding['task_id']}
        or route != {binding['agent'], binding['phase'], 'status:running'}
        or any(x.startswith(('blocker:', 'recovery:', 'watchdog:')) for x in labels)):
        raise HandoffGateError('DECLARED_PUBLICATION_MISMATCH')
    store.assert_operation(binding['operation_key'], row['delivery_id'], row['lease_id'])
    intent['status'] = 'applied'
    checkpoint.pop('projection', None)
    checkpoint.pop('recovery_projection', None)
    if checkpoint.get('start_projection'):
        checkpoint['start_projection']['source_sha'] = intent['to_sha']
    row = store.move_external_head(row['delivery_id'], row['lease_id'],
        intent['from_sha'], intent['to_sha'], checkpoint)
    binding = json.loads(row['payload_json'])
    store.record_recovery_audit(row['delivery_id'], publication_audit(binding, row['lease_id'], intent, 'applied'))
    return row, binding
