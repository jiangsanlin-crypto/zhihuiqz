# Account and Actions host migration (inactive preparation)

## Prepared adapter

`orchestrator.phase_host.run_one` is the common host entry point. It is disabled
by default and does not load a model, execute a command or dispatch a workflow.
An existing authorized executor must supply a cooperative async callback:

```python
await run_one(
    url=approved_control_url, token=dedicated_control_token,
    repository="jiangsanlin-crypto/zhihuiqz",
    phase="phase:code-review", worker_id=stable_host_identity,
    journal_path=persistent_host_journal,
    execute=existing_executor, enabled=explicit_migration_enable,
)
```

The identifiers above are host-injected values, not credentials or live config.
The callback receives `(binding, owned_client)`. It must use the exact bound
repository/PR/SHA, cooperate with cancellation, emit trusted handoff evidence and
return only after evidence publication. It must remove all direct label writes;
start/heartbeat/advance own state projection. Head-changing implementation/repair
uses `owned_client.publish_head`. Existing service checks still gate every phase.
Release and deployment phases are rejected. Foreign-repository candidates are
ignored. Retry journal persistence, expiry and cancellation work identically for
account and Actions hosts.

Prototype/QA callbacks supported here are evidence-only with a stable HEAD.
QA report commits must continue through the native shared-writer path until a
separate external QA publication protocol is implemented. Do not wrap the old
whole workflow unchanged: it contains its own claims/labels/dispatch behavior.

## Actual migration targets and required edits

| Host / workflow | Required integration | State of this PR |
| --- | --- | --- |
| Account Chat Sol GitHub Worker | Run implementation callback through run_one; remove direct label claims | Adapter ready; live task unchanged |
| Work Review Consumer v2 | Run independent review/repair callbacks under owned client | Adapter ready; live task unchanged |
| openai-validator.yml | Extract validation callback; remove direct claim/phase label writes; retain native path for report commits | Shared-mode bridge implemented; activation deferred |
| handoff-reconciler.yml | Delegate projection to the service; never write labels independently | Shared-mode bridge implemented; activation deferred |
| agent-watchdog.yml | Consume recovery observations; no independent label replacement | Shared-mode bridge implemented; activation deferred |
| codex-task.yml | Integrate Issue reservation and confirmation; checkpoint immutable publication receipt | Shared-mode bridge implemented; activation deferred |

The owner subsequently authorized the four workflow edits on PR #83. Their
shared-mode bridge is now implemented, while actual activation remains deferred.
See [shared-workflow-cutover.md](shared-workflow-cutover.md) for mode isolation,
required host callbacks and same-intent planning takeover. This does not mean
live workers or repository variables were switched.

## Abandoned planning confirmation recovery

Periodic discovery now calls `recover_publications` after Issue scanning. An
expired/unowned prepared publication with exactly one matching existing PR is
verified through the same full validator used by explicit confirmation, then
linked transactionally. Original host participation is unnecessary. The recovery
performs only GitHub reads; all mutations are in the service database. Audit keys
include publication identity, candidate PR and outcome, deduplicating repeat scans.

A still-live planning lease is left alone. Missing PR, conflicting associations,
changed Issue/HEAD/body, Human Approval and network uncertainty retain the
reservation and record a waiting reason. Absence from a GET is not proof that an
old publication request will never complete. These cases are not automatically
cancelled or republished; a safe publication-authority takeover/cancellation
protocol remains necessary for that remaining class of abandoned reservation.

## Tests and acceptance distinction

Mocked host tests cover all five supported phases, default-disabled behavior,
foreign repository filtering, denied start and heartbeat cancellation. A real
ASGI claim-router integration test verifies READY -> RUNNING -> evidence-checked
QA READY with shared-writer audits and lease release (GitHub remains mocked).
Planning recovery tests cover orphaned successful publication, live owner,
missing/duplicate/changed evidence, human wait, failures and audit deduplication.
No live executor, workflow, secret store, merge or deployment is invoked by tests.
