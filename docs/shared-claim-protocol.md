# Shared claim protocol

The Orchestrator exposes `/claims/acquire`, `/claims/heartbeat`, and
`/claims/release`. All three require the existing Orchestrator bearer token.
They never start an agent, edit GitHub labels, dispatch Actions or deploy.
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
  This protocol does not implement the sole global label writer or complete
  issue ingestion. Those remain separate acceptance requirements in issue #80.
- Validate competing real workers, restart, network loss and current-SHA
  invalidation after an authorized rollout. No rollout is performed by these
  tests or by adding this interface.
