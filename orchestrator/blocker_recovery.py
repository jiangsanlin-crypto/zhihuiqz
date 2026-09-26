"""Reevaluate registered machine blocker types without guessing human decisions."""
import hashlib
import json
from .state_writer import write_labels
import logging
import uuid
from datetime import datetime, timezone

from scripts.reconcile_handoff_state import decide_reconciliation
from scripts.plan_repair_recovery import decide_repair_recovery
from .external_recovery import _identity, _labels
from .state_store import now
from .task_router import TASK_MARKER

KNOWN = {'recovery:qa-evidence', 'recovery:repair-ci', 'watchdog:timeout'}


async def recover_blockers_once(store, github, repository):
    changed = 0
    for listed in await github.list_open_prs(repository):
        try:
            changed += await _recover_blocker(store, github, repository, listed)
        except Exception as exc:
            # One inaccessible PR must not starve recovery for the rest.
            # Durable projection checkpoints remain available for replay.
            logging.getLogger(__name__).warning('blocker recovery deferred pr=%s error=%s',
                listed.get('number'), type(exc).__name__)
    return changed


async def _recover_blocker(store, github, repository, listed):
    changed = 0
    if 'status:blocked' not in _labels(listed):
        return 0
    pr = await github.get_pr_snapshot(repository, listed['number'])
    labels = _labels(pr)
    if 'status:blocked' not in labels or any(x.startswith('approval:') or x == 'status:review' for x in labels):
        return 0
    codes = {x for x in labels if x.startswith(('recovery:', 'blocker:', 'watchdog:'))}
    sha = (pr.get('head') or {}).get('sha') or ''
    code = next(iter(codes)) if len(codes) == 1 else 'UNCLASSIFIED_OR_MULTIPLE_BLOCKERS'
    if not store.blocker_due(repository, pr['number'], sha, code, sorted(labels)):
        return 0
    observation = {'status': 'waiting', 'last_evaluated_at': now(), 'labels_before': sorted(labels)}
    if len(codes) != 1 or code not in KNOWN:
        observation.update(status='policy_required', reason='unknown/content/multiple blockers cannot be cleared automatically')
        store.observe_blocker(repository, pr['number'], sha, code, observation)
        return 0
    tasks = set(TASK_MARKER.findall(pr.get('body') or ''))
    phases = {x for x in labels if x.startswith('phase:')}
    agents = {x for x in labels if x.startswith('agent:')}
    if len(tasks) != 1 or len(phases) != 1 or len(agents) != 1:
        observation.update(status='policy_required', reason='ambiguous workflow/task')
        store.observe_blocker(repository, pr['number'], sha, code, observation)
        return 0
    binding = dict(repository=repository, pr_number=pr['number'], source_sha=sha,
        head_ref=(pr.get('head') or {}).get('ref'), base_ref=(pr.get('base') or {}).get('ref'),
        task_id=next(iter(tasks)), phase=next(iter(phases)), agent=next(iter(agents)))
    if not _identity(pr, binding):
        return 0
    comments = await github.list_comments(repository, pr['number'])
    runs = await github.list_workflow_runs(repository, sha)
    if code == 'recovery:repair-ci':
        # Old-SHA repair records cannot by themselves authorize recovery.
        exact = [c for c in comments if f'source_sha={sha}' in str(c.get('body') or '').splitlines()]
        if pr.get('mergeable_state') not in {'clean', 'unstable', 'blocked', 'has_hooks'}:
            decision = {'action': 'noop', 'reason': 'mergeability_not_verified'}
        else:
            decision = decide_repair_recovery(pr, exact, runs,
                now=datetime.now(timezone.utc), owner=repository.split('/')[0])
    else:
        decision = decide_reconciliation(pr, comments, repository_owner=repository.split('/')[0], ci_runs=runs)
    observation['reason'] = decision.get('reason') or decision['action']
    target = set(decision.get('labels_after') or [])
    if not target or code in target or 'status:blocked' in target:
        store.observe_blocker(repository, pr['number'], sha, code, observation)
        return 0
    # Recovery only queues execution; never directly enters human approval.
    if 'status:todo' not in target or any(x.startswith('approval:') for x in target):
        store.observe_blocker(repository, pr['number'], sha, code, observation)
        return 0
    evidence = hashlib.sha256(json.dumps([sha, sorted(labels), comments, runs, sorted(target)], sort_keys=True).encode()).hexdigest()
    binding['operation_key'] = json.dumps([repository, pr['number'], sha, binding['phase']], separators=(',', ':'))
    # Stable logical key; resume a lost response, replace only expired attempts.
    request = f"blocker:{pr['number']}:{evidence}"
    previous = store.get(store.external_delivery_id('blocker-reconciler', request))
    if previous and (previous['status'] != 'running' or previous['lease_expires_at'] <= now()):
        request += ':' + str(uuid.uuid4())
    try:
        row = store.claim_external(binding, 'blocker-reconciler', request)
    except RuntimeError:
        return 0
    delivery, lease = row['delivery_id'], row['lease_id']
    projection = json.dumps([repository, pr['number'], 'state-projection'])
    if not store.claim_operation(projection, delivery, lease):
        store.finish(delivery, 'superseded', lease_id=lease)
        return 0
    audit = dict(rule_id='MACHINE_BLOCKER_REEVALUATION', lease_id=lease,
        repository=repository, pr_number=pr['number'], source_sha=sha,
        worker_id='blocker-reconciler', phase=binding['phase'], blocker_codes=[code],
        action_type='unblock', status='planned', reason=observation['reason'],
        labels_before=sorted(labels), labels_after=sorted(target), created_at=now(), evidence_generation=evidence)
    store.checkpoint(delivery, {'blocker_projection': audit}, lease)
    store.record_recovery_audit(delivery, audit)
    finished = False
    try:
        live = await github.get_pr_snapshot(repository, pr['number'])
        if not _identity(live, binding) or _labels(live) != labels:
            finished = True
            return 0
        store.assert_operation(binding['operation_key'], delivery, lease)
        store.assert_operation(projection, delivery, lease)
        await write_labels(store, github, binding, delivery, lease, labels, target)
        live = await github.get_pr_snapshot(repository, pr['number'])
        if not _identity(live, binding) or _labels(live) != target:
            return 0
        audit['status'] = 'applied'
        store.record_recovery_audit(delivery, audit)
        observation.update(status='resolved', labels_after=sorted(target))
        finished = True
        changed += 1
    finally:
        if finished:
            store.finish(delivery, 'done', lease_id=lease)
        store.observe_blocker(repository, pr['number'], sha, code, observation)
    return changed
