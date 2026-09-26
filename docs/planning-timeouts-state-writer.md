# Planning publication, timing and shared state writes

## Planning publication contract

Authenticated `/intake/prepare-publication` accepts the existing intake claim
fields plus `head_ref`, `head_sha`, `base_ref`, and SHA-256 of the exact UTF-8 PR
body (`body_sha256`). It rereads Issue/PR discovery and the repository default
branch, requires the current planning lease, and durably reserves one immutable
publication per issue. Different issues cannot reserve the same branch. Keep the
returned `publication_id` and original claim receipt in the planning host's
restricted durable checkpoint before doing any publication.

The host must publish idempotently to the declared safe branch, using the
repository's authorized planning executor. These endpoints do not create commits,
branches or PRs, execute a model, dispatch Actions or change labels. The PR body
must include the unique `agent-task-id:GH-ISSUE-N` marker and declared plan.

After publication, authenticated `/intake/confirm-publication` accepts the claim
fields, `publication_id` and `pr_number`. It rereads the current Issue revision,
all open associations and the exact PR head/base/body. Only one matching safe
same-repository PR can complete the reservation. Confirmation is idempotent and
observes already-published work; it does not grant an expired planner permission
for another GitHub write. A lost response can therefore be confirmed after
expiry without allowing a replacement planner to duplicate publication.

An unresolved reservation is not advertised as new planning work. A changed Issue,
changed PR body/SHA, fork, protected branch, ambiguous association or Human Approval
fails closed. If the original host never published and cannot resume, the reserved
plan needs explicit resolution; it is not safe to assume a timed-out remote write
never happened. Automatic cancellation/replacement of this uncertainty is not
implemented. Planner execution and deployment remain outside this change.

## One timing policy

`orchestrator/recovery_policy.py` is the common source of timing constants:

| State | Threshold | Decision |
| --- | --- | --- |
| READY without live lease | 15 minutes | Persist warning |
| READY without live lease | 30 minutes | Request consumer scan |
| READY without live lease | 60 minutes | Recovery scan / P1 observation |
| RUNNING without progress | 20 minutes | Persist warning |
| RUNNING without progress | 30 minutes | Verify progress |
| RUNNING, expired tracked lease | 60 minutes | Reconcile durable result or reclaim |
| Machine blocker | 10 minutes | Reevaluate live evidence |
| Claim infrastructure retry | 0, 2, 5, 10, 20 minute delays | Bounded retry of same request |

PR execution leases now last 60 minutes since last server heartbeat, matching the
reclaim policy; this supersedes the former 180-second execution lease. The client
still heartbeats at most every 30 seconds and stops promptly on uncertainty.
Planner leases remain 180 seconds. Expiry never authorizes bypassing CI/Review or
claiming an unknown legacy worker's task.

The periodic monitor persists episode-scoped observations/audit and exposes active
decisions through authenticated `GET /claims/recovery`. READY age starts at first
observation, not PR updated_at; RUNNING age uses a recorded worker heartbeat.
Head/phase/state changes or Human Approval end the old observation episode. A
failed paginated read does not reset timers. Repeated scans do not duplicate a
threshold audit. Existing periodic discovery and expiry recovery remain the
executors; active account hosts must poll the authenticated service. This does
not wake an unconnected host or deliver an external P1 notification.

## Shared state writer coverage

Native Orchestrator transitions, claim start/advance, tracked external recovery
and machine-blocker recovery now call `orchestrator.state_writer.write_labels`.
It obtains the same per-PR projection lock, verifies the event lease and phase
ownership, checks exact head/branch identity and expected labels before/after
writing, rejects illegal target combinations and protects Human Approval. Every
participating write records planned/applied audit. Native writes require a lease;
updated native tests use real SQLite claims rather than unleased mock events.

Labels remain a projection of each caller's verified evidence. The writer does
not itself manufacture CI or review evidence. GitHub offers no transactional
label CAS: an actor bypassing this authority can still race a write. Existing
standalone GitHub Actions and account prompt writers are not migrated by this
PR because workflow changes/live switching remain outside the current scope.
No claim of repository-wide sole-writer or live E2E completion is made.
