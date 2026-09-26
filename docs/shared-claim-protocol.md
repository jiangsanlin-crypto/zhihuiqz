# Shared claim protocol

The Orchestrator exposes `/claims/acquire`, `/claims/heartbeat`,
`/claims/release`, `/claims/start`, and `/claims/advance`. All require its existing bearer token.
The three lease endpoints never edit GitHub labels. The advance endpoint
projects only a verified next phase; none starts an agent, dispatches Actions
or deploys.
The lease grants exclusive ownership, not permission to bypass CI or handoffs.

## Acquire

Send `POST /claims/acquire` with JSON fields:

```json
{
  "repository": "owner/repository",
  "pr_number": 78,
  "source_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "head_ref": "feature/issue-77",
  "task_id": "GH-ISSUE-77",
  "phase": "phase:code-review",
  "worker_id": "account-work-review",
  "request_id": "unique-id-for-this-acquisition"
}
```

The service verifies its configured repository, the open same-repository PR,
safe head branch, exact SHA, task marker, and one canonical READY route. It
rejects human approval and blocker labels. Supported phases are implementation,
code review, escalation repair, prototype and QA; release/deploy are excluded.

The operation key is the JSON tuple `[repository, pr_number, source_sha, phase]`,
identical to the native Orchestrator key. An active native or external lease
prevents another owner from acquiring it. A retry with the same worker/request
ID returns its existing live lease; changing the bound task under that request
ID fails. Expired/ended requests require a new request ID.

Response fields: `delivery_id`, `lease_id`, `lease_expires_at`.
The server rechecks GitHub after acquisition; changed inputs revoke the lease.

## Heartbeat and release

Both endpoints accept `delivery_id`, `lease_id`, and `worker_id` from acquisition.
Heartbeat every 30 seconds while working; the lease lasts 180 seconds from its
last accepted renewal. The service checks the live SHA, branch, task and route
before renewal. A changed HEAD, blocker or human-wait state revokes the lease.
Release finishes ownership without changing labels or advancing the task.

On HTTP 401 stop: authentication is invalid. On HTTP 409 stop this attempt:
ownership or live state no longer matches. Never continue writing after a lost
lease. Treat transport failures as uncertain; retry the same acquisition ID,
and stop execution before the last confirmed expiry if renewal is unavailable.
Before every write, workers must also re-fetch the PR and verify its head/state;
a successful heartbeat is not an atomic GitHub write authorization.

## Start execution

After acquisition, call `POST /claims/start` with the same ownership fields.
Only execute after a successful response and while the confirmed lease is live.
This projects the claimed READY route to RUNNING without releasing the lease.
It uses the same per-PR projection lock as advancement, records planned/applied
audit evidence, preserves unrelated labels, and rechecks SHA, state and ownership
before writing. QA additionally requires live exact-SHA ordinary CI and independent
Review evidence. Other workers must still validate their phase's prerequisites;
this endpoint never starts an agent or grants downstream approval.

Retry uncertain start responses with the same live lease. A recorded RUNNING
projection is verified without another label PUT. Completed starts cannot undo a
subsequent requeue. An expired lease, changed HEAD, human wait or label drift fails
closed. Do not execute after a failed or uncertain start. A worker dying after
RUNNING still requires the authoritative recovery controller to reclaim it; this
endpoint alone is not that controller. Legacy writers remain an integration gate.

## Verified advancement

After publishing the required trusted handoff, call `POST /claims/advance`
with the same three ownership fields as heartbeat. Arbitrary labels are not
accepted. The service derives the next route from current-SHA CI and evidence:

- Prototype success -> implementation READY.
- Implementation success -> independent Work Review READY.
- Repair with a trusted waiting-CI record -> independent Work Review READY.
- Independent Work Review PASS -> QA READY.
- QA PASS plus independent Review and a resolved stop-after-QA/owner-approval
  policy -> Human Approval. There is no release/deploy transition here.

Review workers must still publish their authenticated GitHub review claim and
independent PASS handoff. The service lease alone is not that review evidence.

Participating phase writers share a per-PR projection lock. The service saves
the intended projection before one label PUT, checks the live state again,
and verifies the result. Planned/applied records with worker, lease, SHA,
evidence generation and before/after labels are durably retained in SQLite.
If the network response is lost after the PUT, retry `/claims/advance` while
the lease remains valid; it can verify the existing target without another PUT.
After completion, the phase lease is released. An exact retry returns the
historical `already_applied` result without writing or exiting Human Approval.
Stop phase execution/heartbeats after advancement; the next phase acquires its
own lease and independently validates its gates.

## Required integration before repository-wide acceptance

- Deploy one authoritative service backed by persistent storage, or replicas
  sharing the supported local SQLite database. Independent databases do not
  coordinate claims. Do not put SQLite on an unsupported network filesystem.
- Account workers and Actions must acquire here before starting work and retain
  the returned lease through execution. Existing actors are not migrated merely
  because these endpoints exist in a PR.
- Native Orchestrator operations already use the same operation lock table.
  External claim rows are never put into its agent-execution queue on expiry.
- Keep phase-specific CI, independent review, handoff and terminal-policy gates.
  The projection endpoint exists, but existing workflows still bypass it.
  Until every writer adopts it, it is not the sole global writer. GitHub label
  PUT has no conditional CAS; pre/post checks cannot prevent every race with
  nonparticipating actors. Complete issue ingestion also remains open in #80.
- Validate competing real workers, restart, network loss and current-SHA
  invalidation after an authorized rollout. No rollout is performed by these
  tests or by adding this interface.

## Discovery and account client integration

`GET /claims/ready` uses the same bearer authentication. It paginates open PRs
and returns canonical READY candidates with one task marker, safe same-repository
head and exact SHA. Drafts, human approval, conflicting routes, blockers and
release/deployment phases are excluded. Discovery is read-only: candidates are
not claims and must pass the live acquisition checks.

The native Orchestrator now scans once per minute in its lifespan. It durably
queues only prototype/QA candidates for its **existing** worker, using a stable
repository/PR/SHA/phase/task identity. Duplicate scans do not reset exhausted
attempts. Account phases are never executed by this scanner. An exception in a
scan is retried on the next scan without logging response payloads or credentials.

`orchestrator.claim_client.ClaimClient` supplies an account-host integration:

```python
client = ClaimClient(service_url, service_token)  # injected by the host
try:
    result = await client.consume_one("phase:code-review", worker_id, review)
finally:
    await client.close()
```

The host provides a cooperative async `review(binding)` worker that reads its
required inputs, performs independent review and publishes its trusted exact-SHA
handoff before returning. `consume_one` discovers work, skips stale/busy claims,
starts through the service, renews during work and requests verified advancement.
It never invokes a model itself. Acquisition transport/429/5xx failures retry the
same request ID with bounded backoff; 401/409 fail without retry. Heartbeat failure
or expiry cancels work and prevents advancement. Host write operations must still
be cancellation-aware and independently check HEAD; Python cancellation cannot
fence an unrelated remote process or a noncooperative synchronous callback.

This client is integrated with the real claim router in mocked-GitHub tests.
**Existing account schedules and Actions have not been switched to this client.**
Their host configuration and the authoritative service deployment are required.
Do not silently fall back to direct label writes after adopting this protocol.

A phase that changes HEAD outside the declared publication protocol below stops
and cannot advance under its old binding. Implementation/repair workers can now
use the declared-commit protocol; actual host adoption remains required. The client does not itself recover expired RUNNING tasks; the service scanner
now handles tracked same-SHA expired claims as described below. Arbitrary
machine-blocker recovery remains incomplete.

Native workers now persist a `starting` checkpoint before projecting RUNNING.
After a crash on either side of that write, the same durable event is reclaimed
under a new lease and revalidates the live branch/state and phase evidence.
All returned agent results are saved, including failures or results with no file
changes, so a comment failure does not rerun completed work. A crash before an
adapter returns may still require adapter-level idempotency on replay.


## Expired external lease recovery

Each discovery cycle also checks up to 100 expired external leases. A database
CAS gives one reconciler a fresh lease and changes ownership so acquisition
retries from the old worker cannot adopt the recovery lease. The controller
checks the live branch, SHA, task and canonical state, and shares the operation
and per-PR projection locks. It never starts an agent.

- With no trusted current-SHA phase result, a tracked RUNNING task returns to
  its phase's READY state, enabling a new worker request to claim it.
- With a durable result, the controller validates fresh CI/handoff/review/policy
  gates and applies the verified next phase. It does not rerun completed work.
- If the result does not authorize advancement, it retains the state, audits
  waiting_evidence and reevaluates after the recovery lease expires. A failed
  result is not automatically retried as if it had succeeded.
- Planned/applied recovery records let a lost label-write response resume without
  repeating the PUT. HEAD changes and human wait stop old-phase recovery.

Unknown legacy RUNNING tasks without service start/projection evidence are not
reclaimed. Global blocker routing, unregistered/concurrent HEAD changes and removal of
nonparticipating label writers remain separate acceptance gates. GitHub label
PUT still has no CAS against those writers.


## Declared commit publication and exact-SHA transfer

Only implementation and escalation-repair leases may publish code. Independent
review leases cannot use this protocol to approve their own edits.

1. The owning host creates an immutable commit object whose single parent is
   the claimed SHA, without moving any ref. Revalidate the PR identity first.
2. POST `/claims/prepare-head` with ownership fields plus `target_sha`. The server
   requires its applied RUNNING start record, validates that exact commit and all
   changed paths, and saves the intent before branch publication. Workflow files
   (including renamed-from workflow paths) are forbidden. Missing/truncated path
   listings and merge/unrelated commits fail closed. No GitHub write is performed.
3. The host rechecks branch/HEAD/base and publishes only that commit by a
   non-forced update of the existing PR head ref.
4. POST `/claims/confirm-head` with ownership fields. The server accepts only
   the exact predeclared SHA, same branch/base/task and RUNNING phase. It atomically
   moves ownership to the new operation key, refusing any other live owner.
5. Publish handoff/check evidence for the returned `source_sha`. Old CI, Review
   and QA evidence has no advancement eligibility. Implementation and repair
   still advance only to fresh independent Review, never straight to QA.

`ClaimClient.publish_head(target_sha, publish)` wires steps 2–4 around a
cooperative host `publish()` callback and updates the binding passed to the
worker. The callback must be cancellation-aware and perform the ref safety
checks; the library never performs a GitHub write itself. Heartbeat can confirm
a declared push if the confirmation response is lost. If the worker dies, the
expired-lease reconciler verifies that same intent before recovering the new SHA.
Unregistered concurrent commits, base retargets, task changes or Human Approval
are not adopted. Confirmations are idempotent, including heartbeat/confirm races.

The server records prepared/applied invalidation audit entries and retains the
old-SHA history. This proves a controlled publication path in branch tests, not
that existing account hosts have adopted it or that deployment is authorized.

## Durable Issue intake

The service periodically reads all open issues and PRs. Owner-authored issues
with a nonempty task body and no human/blocker wait enter `awaiting_planner`.
Other authors require triage. Exact task markers and closing references link
existing PRs; weak/multiple references enter `needs_link_resolution`. Previously
observed associations survive disappearance/closure/reopening so discovery cannot
silently plan a duplicate PR. A failed full scan never closes unseen queue rows.

Authenticated endpoints (same bearer policy as `/claims`):

- `GET /intake/issues`: revision, disposition and claimable status; no lease tokens.
- `POST /intake/acquire`: `issue_number`, 64-character `generation`, `worker_id`,
  and a fresh random `lease_id` (16–150 safe characters). Re-fetches issues/PRs,
  then performs database CAS. Same live request is idempotent; a second owner is
  rejected. Expired attempts require a new token.
- `POST /intake/heartbeat`: same body; rechecks the issue revision and association
  before renewal. Body/label/closure/PR-link changes fence the old planning lease.

The lease lasts 180 seconds. Planning hosts must heartbeat and stop on uncertainty,
recheck before publishing, and use the same service/database. The service does
not execute a planner or create a branch/PR. The existing planning host has not
been connected; this API alone is not Issue-to-PR completion. GitHub publication
by an uncooperative host is not fenced by a SQLite lease.

## Durable account-host acquisition journal

Account hosts should construct `ClaimRetryJournal` on a persistent local path
and pass it as `retry_journal` to `ClaimClient`. It stores only the immutable
binding hash, worker/request ID, attempt index, enumerated outcome and timestamp;
never tokens, exception bodies, repository content or model output.

Transport/429/5xx failures consume the bounded retry budget. A restart resumes
recorded retries rather than starting the same request at attempt zero. Exhausted
requests persist `WORKER_ACQUISITION_FAILED`; stale/auth responses end that request
without retry. `consume_one` uses this journal after fresh READY discovery: it
resumes uncertain attempts, skips ended bindings during a ten-minute cooldown,
and permits a new request only after another fresh discovery. Each acquisition
still performs server-side live SHA/state/lease validation. A new SHA has a new
binding. No labels, fake result or workflow are written by the journal.

This is a durable host-side recoverable acquisition condition, not a GitHub
`status:blocked` projection. When the service itself is unreachable, pretending
it durably received a blocker would be incorrect. Hosts must preserve this file;
without `retry_journal`, compatibility callers retain in-memory retry behavior.
The journal is not a distributed lock: the authoritative claim service remains
responsible for excluding competing workers. Multi-host audit aggregation and
remaining R01/R04 policies still require integration.
