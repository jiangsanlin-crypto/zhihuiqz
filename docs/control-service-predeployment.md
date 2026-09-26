# Control service preparation (no rollout authorization)

## Isolated service entry point

`orchestrator.control_service:create_app` is an ASGI factory. It does not import
or start the native agent executor. Use the repository's pinned requirements and
`uvicorn orchestrator.control_service:create_app --factory` in a separately
approved deployment. Do not run this command against the live service during
preparation.

Configuration contract:

| Setting | Required value / behavior |
| --- | --- |
| CONTROL_REPOSITORY | Exact owner/repository |
| CONTROL_BUILD_SHA | Reviewed 40-character commit SHA; no `latest` alias |
| CONTROL_STATE_DB | Durable shared SQLite path; never independent databases for competing workers |
| CONTROL_WRITES_ENABLED | Defaults to false; enable only during authorized migration |
| /run/secrets/control_token | Dedicated service bearer file, mounted read-only |
| /run/secrets/control_github_token | Dedicated repository credential file, mounted read-only |

No shared environment bundle or OpenAI credential is loaded by the factory.
Terminate TLS at the approved ingress; do not expose the HTTP listener directly.
Preflight mode starts no scanner/worker and rejects all non-GET/HEAD requests.
Authenticated discovery can still perform read-only GitHub requests. `/readyz`
reports protocol/repository/build/write mode and database schema accessibility;
it is not a claim that GitHub, workers or live E2E are healthy.

Even in active mode this standalone controller does not enqueue native work
without an executor. Account-host adoption and the native Validator integration
must be accepted separately. Switching the write flag is not full migration.

## Connection check after authorization

From each actual account host, use the dedicated service credential and:

```
python scripts/check_worker_service.py --url https://CLAIM_SERVICE --token-file /secure/control-token --expected-sha REVIEWED_SHA --repository jiangsanlin-crypto/zhihuiqz
```

This is a command template, not a discovered service endpoint. The check uses GET
only, rejects redirects and validates protocol/build/repository. No credentials
or task bodies are emitted. Do not update worker prompts until host reachability
and client execution/heartbeat capabilities are independently verified.

## Durable state and rollback procedure

Before an authorized write-enabled rollout, stop new claims and drain workers.
Back up the database using `scripts/backup_control_state.py --source DB_PATH
--destination NEW_BACKUP_PATH`. The SQLite backup API includes WAL contents,
checks integrity and required tables, writes mode 0600, and refuses replacement.
Do not copy only the main SQLite file while a WAL is active. Backups contain lease
and workflow data and belong in the approved restricted backup location.

On failure, disable writes and stop participating workers. Preserve the current
DB and audit history; return to the last reviewed binary with writes disabled.
Do not blindly restore an old DB while workers continue: old leases/claims could
be revived or acknowledged GitHub effects forgotten. Test restoration to an
isolated path with all workers stopped, then reconcile current GitHub SHA/state
and require fresh ownership before any approved resumption. Never automatically
resume legacy label writers as a rollback shortcut. No script here deploys,
restores live state, merges a PR or changes a GitHub workflow.

## Verified locally versus outstanding

Local tests exercise default deny-write behavior, no executor startup, shutdown,
build identity, endpoint auth, mutation attempts, SQLite connection cleanup,
WAL backup/validation and the existing queue/lease/recovery regressions.

Still outstanding before declaring the complete #80 preparation finished:
actual planner publication/association protocol, exhausted acquisition recovery,
full R01/R04 policy wiring, remaining blocker policies, migration of every state
writer and independent review. Live connectivity and end-to-end acceptance are
explicitly deferred by the owner's no-deployment instruction. This document does
not convert those outstanding implementation tasks into completed items.
