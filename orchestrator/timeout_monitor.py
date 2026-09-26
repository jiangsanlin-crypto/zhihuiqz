"""Persist timing decisions; callers act only through existing leased endpoints."""
import hashlib
import json

from .recovery_policy import elapsed, timeout_action
from .state_store import now
from .task_router import label_names, TASK_MARKER


async def monitor_timeouts(store, github, repository):
    # Obtain a complete snapshot before expiring an observation episode.
    prs=await github.list_open_prs(repository)
    timestamp=now();seen=[];count=0
    with store.lock, store.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        for pr in prs:
            labels=set(label_names(pr.get('labels')))
            states={x for x in labels if x.startswith('status:')}
            phases={x for x in labels if x.startswith('phase:')}
            head=pr.get('head') or {}
            if (pr.get('state')!='open' or pr.get('draft') or pr.get('merged_at')
                or (head.get('repo') or {}).get('full_name')!=repository
                or head.get('ref') in {'main',(pr.get('base') or {}).get('ref'),(head.get('repo') or {}).get('default_branch')}
                or len(set(TASK_MARKER.findall(pr.get('body') or '')))!=1
                or len({x for x in labels if x.startswith('agent:')})!=1
                or any(x.startswith('approval:') for x in labels)
                or states not in ({'status:todo'},{'status:running'}) or len(phases)!=1):
                continue
            phase=next(iter(phases))
            if phase not in {'phase:prototype','phase:implementation','phase:code-review','phase:escalation-repair','phase:qa'}:
                continue
            status=next(iter(states)).removeprefix('status:')
            key=json.dumps([repository,pr['number'],head.get('sha'),phase,status])
            seen.append(key)
            old=db.execute('SELECT * FROM timeout_observations WHERE operation_key=?',(key,)).fetchone()
            first=old['first_seen'] if old and old['active'] else timestamp
            episode=hashlib.sha256((key+first).encode()).hexdigest()
            binding_key=json.dumps([repository,pr['number'],head.get('sha'),phase],separators=(',',':'))
            lease=db.execute('''SELECT e.* FROM operation_claims c JOIN events e ON c.delivery_id=e.delivery_id
                AND c.lease_id=e.lease_id WHERE c.operation_key=? AND e.status='running' ''',(binding_key,)).fetchone()
            live=bool(lease and lease['lease_expires_at']>timestamp)
            # Heartbeat time, never PR updated_at (comments can change it).
            age=elapsed(lease['updated_at'] if status=='running' and lease else first)
            action=timeout_action(status,age,live_lease=live,tracked=lease is not None)
            db.execute('''INSERT INTO timeout_observations VALUES(?,?,?,?,1,?)
                ON CONFLICT(operation_key) DO UPDATE SET first_seen=excluded.first_seen,
                last_seen=excluded.last_seen,action=excluded.action,active=1,payload_json=excluded.payload_json''',
                (key,first,timestamp,action,json.dumps(dict(repository=repository,pr_number=pr['number'],
                 source_sha=head.get('sha'),phase=phase,status=status,episode=episode))))
            if action!='none':
                count+=db.execute('INSERT OR IGNORE INTO timeout_audit VALUES(?,?,?,?)',
                    (episode+':'+action,key,action,timestamp)).rowcount
        rows=db.execute('SELECT operation_key,payload_json FROM timeout_observations WHERE active=1').fetchall()
        for row in rows:
            if json.loads(row['payload_json'])['repository']==repository and row['operation_key'] not in seen:
                db.execute('UPDATE timeout_observations SET active=0 WHERE operation_key=?',(row['operation_key'],))
    return count
