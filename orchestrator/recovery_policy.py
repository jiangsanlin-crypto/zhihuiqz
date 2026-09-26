"""One timing policy for recovery decisions; no GitHub writes or worker launch."""
from datetime import datetime, timezone

READY_WARNING = 15 * 60
READY_SCAN = 30 * 60
READY_ESCALATE = 60 * 60
RUNNING_WARNING = 20 * 60
RUNNING_VERIFY = 30 * 60
RUNNING_RECLAIM = 60 * 60
BLOCKER_REEVALUATE = 10 * 60
CLAIM_RETRY_DELAYS = (0, 120, 300, 600, 1200)


def timeout_action(status, seconds, *, live_lease=False, tracked=False, durable_result=False, human_wait=False):
    if human_wait or seconds < 0:
        return 'none'
    if status == 'todo':
        if live_lease: return 'none'
        if seconds >= READY_ESCALATE: return 'recovery_scan_p1'
        if seconds >= READY_SCAN: return 'scan_consumer'
        if seconds >= READY_WARNING: return 'warn_ready'
    elif status == 'running':
        if seconds >= RUNNING_RECLAIM and not live_lease:
            if not tracked: return 'ownership_verification_required'
            return 'reconcile_result' if durable_result else 'reclaim'
        if seconds >= RUNNING_VERIFY: return 'verify_progress'
        if seconds >= RUNNING_WARNING: return 'warn_running'
    return 'none'


def elapsed(timestamp, current=None):
    try:
        then=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
        return max(0,((current or datetime.now(timezone.utc))-then).total_seconds())
    except (AttributeError,TypeError,ValueError):
        return 0
