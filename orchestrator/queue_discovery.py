"""Read-only discovery plus durable scheduling for the existing native worker.

Account phases are exposed for account consumers, never run by this process.
"""
import asyncio
import hashlib
import json
import logging
import re

from .task_router import TASK_MARKER, label_names
from .external_recovery import recover_external_once
from .issue_intake import scan_issues
from .blocker_recovery import recover_blockers_once
from .timeout_monitor import monitor_timeouts
from .planning_recovery import recover_publications

ROUTES = {
    'phase:implementation': 'agent:chatgpt',
    'phase:code-review': 'agent:workreview',
    'phase:escalation-repair': 'agent:workreview',
    'phase:prototype': 'agent:workbuddy',
    'phase:qa': 'agent:workbuddy',
}


def candidate(pr, repository):
    head, base = pr.get('head') or {}, pr.get('base') or {}
    head_repo = head.get('repo') or {}
    labels = set(label_names(pr.get('labels')))
    markers = set(TASK_MARKER.findall(pr.get('body') or ''))
    phases = labels & ROUTES.keys()
    if (pr.get('state') != 'open' or pr.get('merged_at') or pr.get('draft')
        or head_repo.get('full_name') != repository or len(markers) != 1
        or not head.get('ref') or head.get('ref') in {'main', base.get('ref'), head_repo.get('default_branch')}
        or not re.fullmatch('[0-9a-f]{40}', head.get('sha') or '')
        or len(phases) != 1 or type(pr.get('number')) is not int
        or any(x.startswith(('blocker:', 'recovery:', 'watchdog:')) for x in labels)):
        return None
    phase = next(iter(phases))
    route = {x for x in labels if x.startswith(('agent:', 'phase:', 'status:', 'approval:'))}
    if route != {ROUTES[phase], phase, 'status:todo'}:
        return None
    return dict(repository=repository, pr_number=pr['number'], source_sha=head['sha'],
                head_ref=head['ref'], task_id=next(iter(markers)), phase=phase)


async def discover(github, repository):
    return [(pr, binding) for pr in await github.list_open_prs(repository)
            if (binding := candidate(pr, repository))]


async def scan_once(store, github, repository):
    queued = 0
    for pr, binding in await discover(github, repository):
        # No account model, API programmer, release or deployment invocation.
        if binding['phase'] not in {'phase:prototype', 'phase:qa'}:
            continue
        key = json.dumps([repository, binding['pr_number'], binding['source_sha'], binding['phase']], separators=(',', ':'))
        if store.operation_active(key):
            continue
        identity = json.dumps([binding, store.queue_generation(binding)], sort_keys=True)
        delivery = 'queue-scan:' + hashlib.sha256(identity.encode()).hexdigest()
        queued += store.enqueue(delivery, 'pull_request', {
            'action': 'labeled', 'number': pr['number'], 'pull_request': pr,
            'label': {'name': 'status:todo'}, 'repository': {'full_name': repository},
        })
    return queued


async def discovery_loop(stop, store, github, repository, interval=60, *, native_queue=True):
    actions = (scan_issues, recover_publications, monitor_timeouts, recover_external_once, recover_blockers_once)
    if native_queue:
        actions += (scan_once,)
    while not stop.is_set():
        for action in actions:
            try:
                await action(store, github, repository)
            except Exception:
                # A failed issue scan must not starve ready PRs or recovery.
                logging.getLogger(__name__).warning('queue discovery step failed: %s', action.__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
