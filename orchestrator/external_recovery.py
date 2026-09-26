"""Recover only expired external claims recorded by this authoritative store.

Never invokes a worker. Unknown/unleased legacy RUNNING tasks are not adopted.
"""
import hashlib
import json
import logging

from .handoff_gate import HandoffGateError, extract_handoff
from .state_projection import verified_next_workflow
from .state_store import now
from .task_router import TASK_MARKER, label_names


def _labels(pr):
    return set(label_names(pr.get('labels')))


def _route(labels):
    return {x for x in labels if x.startswith(('agent:', 'phase:', 'status:', 'approval:'))}


def _identity(pr, binding):
    head, base = pr.get('head') or {}, pr.get('base') or {}
    repo = head.get('repo') or {}
    return (pr.get('state') == 'open' and not pr.get('merged_at')
        and repo.get('full_name') == binding['repository']
        and head.get('sha') == binding['source_sha']
        and head.get('ref') == binding['head_ref']
        and head.get('ref') not in {'main', base.get('ref'), repo.get('default_branch')}
        and set(TASK_MARKER.findall(pr.get('body') or '')) == {binding['task_id']})


def durable_result(binding, comments):
    phases = {'phase:prototype': 'prototype_validation', 'phase:implementation': 'implementation',
              'phase:code-review': 'code_review', 'phase:qa': 'qa_acceptance'}
    owner = binding['repository'].split('/', 1)[0]
    trusted = {owner} if binding['agent'] in {'agent:chatgpt', 'agent:workreview'} else {owner, 'github-actions[bot]'}
    for comment in comments:
        if (comment.get('user') or {}).get('login') not in trusted:
            continue
        body = comment.get('body') or ''
        if binding['phase'] == 'phase:escalation-repair':
            lines = set(body.splitlines())
            if ('<!-- agent-repair:v1 -->' in body and
                {f"task_id={binding['task_id']}", f"source_sha={binding['source_sha']}",
                 'agent=workreview', 'phase=escalation-repair'} <= lines):
                return True
        try:
            value = extract_handoff(body)
        except HandoffGateError:
            continue
        if (value and value.get('task_id') == binding['task_id']
            and value.get('source_sha') == binding['source_sha']
            and value.get('phase') == phases.get(binding['phase'])
            and value.get('from_agent') == binding['agent'].removeprefix('agent:')
            and value.get('pr_number') in (None, binding['pr_number'])):
            return True
    return False


async def recover_external_once(store, github, repository):
    recovered = 0
    for old in store.expired_external_claims():
        binding = json.loads(old['payload_json'])
        if binding.get('repository') != repository:
            continue
        row = store.reclaim_external(old['delivery_id'], old['lease_id'])
        if not row:
            continue
        try:
            recovered += await _recover(store, github, row, binding)
        except Exception as exc:
            # Keep the durable checkpoint and a bounded lease. Next expiry retries
            # it; no exception payload/credential is logged or sent to GitHub.
            logging.getLogger(__name__).warning('external lease recovery deferred: %s', type(exc).__name__)
            continue
    return recovered


async def _recover(store, github, row, binding):
    delivery, lease = row['delivery_id'], row['lease_id']
    checkpoint = json.loads(row.get('checkpoint_json') or '{}')
    op = binding['operation_key']
    projection_key = json.dumps([binding['repository'], binding['pr_number'], 'state-projection'])
    if not store.claim_operation(op, delivery, lease):
        store.finish(delivery, 'superseded', lease_id=lease)
        return 0
    if not store.claim_operation(projection_key, delivery, lease):
        return 0
    pr = await github.get_pr_snapshot(binding['repository'], binding['pr_number'])
    before = _labels(pr)
    # Human wait, HEAD movement and ambiguous routes are never repaired by
    # replaying an old phase. Leave their labels untouched.
    running = {binding['agent'], binding['phase'], 'status:running'}
    todo = {binding['agent'], binding['phase'], 'status:todo'}
    prior = checkpoint.get('recovery_projection') or {}
    accepted = [running, todo]
    if prior:
        accepted.append(set(prior['workflow_after']))
    phase_projection = checkpoint.get('projection') or {}
    if phase_projection:
        accepted.append(set(phase_projection['workflow_after']))
    if (not _identity(pr, binding) or _route(before) not in accepted
        or any(x.startswith(('approval:', 'blocker:', 'recovery:', 'watchdog:')) for x in before)):
        store.finish(delivery, 'superseded', lease_id=lease)
        return 0
    if not (checkpoint.get('start_projection') or phase_projection) and _route(before) == running:
        # No proof our lease projected this RUNNING state: no ownership guess.
        store.finish(delivery, 'superseded', lease_id=lease)
        return 0
    comments = await github.list_comments(binding['repository'], binding['pr_number'])
    runs = await github.list_workflow_runs(binding['repository'], binding['source_sha'])
    has_result = durable_result(binding, comments)
    if has_result:
        try:
            target = verified_next_workflow(binding, comments, runs)
        except HandoffGateError:
            # Preserve durable failure/blocked/PENDING evidence without rerunning
            # the phase. Later scans reevaluate current evidence after expiry.
            store.record_recovery_audit(delivery, dict(
                rule_id='EXPIRED_EXTERNAL_LEASE', lease_id=lease,
                repository=binding['repository'], pr_number=binding['pr_number'],
                source_sha=binding['source_sha'], worker_id='lease-reconciler',
                phase=binding['phase'], action_type='reevaluate',
                status='waiting_evidence', reason='durable result does not yet authorize advancement',
                labels_before=sorted(before), labels_after=sorted(before), created_at=now(),
                evidence_generation=hashlib.sha256(json.dumps(
                    [binding['source_sha'], comments, runs], sort_keys=True).encode()).hexdigest()))
            return 0
        reason = 'expired lease; verified durable phase result'
    else:
        if _route(before) not in (running, todo):
            return 0
        target = todo
        reason = 'expired lease; no durable current-SHA phase result'
    after = (before - _route(before)) | target
    audit = dict(rule_id='EXPIRED_EXTERNAL_LEASE', lease_id=lease,
        repository=binding['repository'], pr_number=binding['pr_number'],
        source_sha=binding['source_sha'], task_id=binding['task_id'],
        worker_id='lease-reconciler', phase=binding['phase'], operation_key=op,
        action_type='recover', reason=reason, status='planned', created_at=now(),
        labels_before=sorted(before), labels_after=sorted(after), workflow_after=sorted(target),
        evidence_generation=hashlib.sha256(json.dumps([binding['source_sha'], comments, runs, sorted(target)], sort_keys=True).encode()).hexdigest())
    checkpoint['recovery_projection'] = audit
    store.checkpoint(delivery, checkpoint, lease)
    store.record_recovery_audit(delivery, audit)
    live = await github.get_pr_snapshot(binding['repository'], binding['pr_number'])
    if not _identity(live, binding) or _labels(live) != before:
        return 0
    store.assert_operation(op, delivery, lease)
    store.assert_operation(projection_key, delivery, lease)
    if before != after:
        await github.set_labels(binding['repository'], binding['pr_number'], sorted(after))
    verified = await github.get_pr_snapshot(binding['repository'], binding['pr_number'])
    if not _identity(verified, binding) or _labels(verified) != after:
        return 0
    store.assert_lease(delivery, lease)
    audit['status'] = 'applied'
    audit['applied_at'] = now()
    store.record_recovery_audit(delivery, audit)
    store.checkpoint(delivery, checkpoint, lease)
    store.finish(delivery, 'done', lease_id=lease)
    return 1
