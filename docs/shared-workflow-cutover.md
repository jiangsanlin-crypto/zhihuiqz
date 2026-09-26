# Reviewed workflow migration and planning recovery

This is PR-branch preparation. No repository variable, live worker, service,
secret, merge or deployment is changed by committing these files.

## Four workflow entry points

`openai-validator.yml`, `codex-task.yml`, `handoff-reconciler.yml` and
`agent-watchdog.yml` now use one repository-level `CONTROL_WORKFLOW_MODE`:

| Mode | Legacy jobs | Shared controller job |
| --- | --- | --- |
| Unset or `legacy` | Original event conditions apply | Disabled |
| `shared` | Disabled, including direct label writers | Enabled |
| Any other value | Disabled | Explicit configuration failure |

No shared failure falls back to legacy execution. The shared job has only
`contents: read`, checks a reviewed 40-character revision, checks out that exact
`CONTROL_BUILD_SHA` without persisted credentials, and calls the controller with
a dedicated `CONTROL_SERVICE_TOKEN`. The retired implementation workflow is
unchanged. Shared mode invokes no model, API programmer, GitHub dispatch or release.

The bridge validates HTTPS/no redirects, repository, build, protocol and enabled
write mode. `POST /control/wake` has bearer authentication, repository/build fences,
a shared SQLite tick lease and persisted delivery receipts. Successful repeated
GitHub delivery IDs do not duplicate a tick; evidence failures return an error and
can retry. A tick only runs discovery and recovery; a successful receipt means
controller acknowledgement, not that an agent completed a task.

## Activation prerequisites (not performed)

After separate rollout authorization: deploy the reviewed service; configure its
persistent database and dedicated credentials; install approved planner and
prototype/QA/account host callbacks; verify their actual polling/heartbeat and
handoff behavior. `phase_host` does not itself supply those model executors.
Drain all already-running legacy jobs and stop their independent label writers
before setting the shared-mode variable. Job conditions are evaluated at start;
a mode change cannot cancel or fence an old job already running.

Only then set the approved HTTPS `CONTROL_SERVICE_URL`, reviewed
`CONTROL_BUILD_SHA`, dedicated service secret and `CONTROL_WORKFLOW_MODE=shared`.
This document is not permission to set them now. Mixed legacy/shared writers are
not a supported intermediate state. External QA report commits remain on the
native shared-writer path; the external adapter's QA callback is evidence-only.

## Unpublished planning takeover

Authenticated `GET /intake/publications` exposes immutable publication intents,
not owner credentials. `POST /intake/resume-publication` accepts the Issue number,
generation, publication ID, a new worker ID and fresh lease ID. It refreshes Issue
association and checks **all PR history** for the declared branch, including closed
PRs, plus the branch's current SHA and repository default branch. Then a database
CAS transfers the expired planning lease and reservation ownership.

The replacement must use the original declared ref/SHA/body digest. It cannot
choose an alternate branch, force-push, change the plan or overwrite a conflicting
HEAD. If the declared ref is absent, the receipt allows creation of that one ref
at that one immutable SHA. Missing artifacts must be recovered and verified before
publication; the receipt does not recreate them.

`planning_host.resume_one` is the opt-in cooperative polling adapter. It renews
the transferred lease while the host reproduces/publishes the exact intent,
cancels on ownership uncertainty, and confirms the returned PR. The publisher
callback must recheck branch/PR state and call its supplied guard before writes.
Old planner receipts can no longer confirm through the service. This cannot revoke
GitHub access from an unmanaged, noncooperative process; such a process must be
stopped before takeover.

## Evidence conflicts

- Existing exact-match publication: automatic confirmation by the scanner.
- Current HEAD is a verified descendant of the declared planning commit, while
  branch/body/Issue association remain unchanged: automatic **association**
  confirmation. Original CI/Review/QA eligibility is never transferred to the new
  SHA, and no PR labels are changed by this recovery.
- No publication history and unchanged Issue/branch: leased same-intent takeover.
- Diverged branch, changed Issue/body, multiple associations, historical closed PR,
  protected branch or Human Approval: fail closed with an explicit reason. Do not
  erase evidence or create a second PR merely to remove a blocked status.

These last cases need a new authorized task decision or resolution of contradictory
evidence. Automatically guessing which user change to discard is not recovery.

## Verification

Tests cover exclusive workflow modes, pinned checkout, read-only job permissions,
authentication/build validation, tick idempotency and contention, no redirect or
legacy fallback, real-router planning takeover/confirmation, old-owner fencing,
closed-PR protection, SHA conflict, network failure and descendant association.
All network/model/publication effects in tests are mocked; no workflow is dispatched.
