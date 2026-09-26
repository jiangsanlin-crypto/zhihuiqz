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
