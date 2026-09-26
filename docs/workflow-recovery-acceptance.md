# Workflow recovery acceptance for issue #80

## Completion rule

Keep #80 open until a real task reaches owner wait with ordinary CI,
independent Work Review, the review handoff and QA evidence all bound to the
final HEAD. Owner wait requires an explicit resolved terminal policy and no
active agent, phase or lease. Failed, pending and action-required checks do not
satisfy this rule. Do not merge or deploy as part of this repair task.

## Implemented regression coverage

- READY discovery accepts the final agent, phase or todo label and rejects
  conflicting routes, human-wait states and unrelated label events.
- Orchestrator QA requires current-SHA ordinary CI and a trusted independent
  Work Review claim/PASS. Reconciliation uses the same ordinary CI predicate.
- A machine QA-evidence blocker can recover only after both gates pass; a
  content blocker cannot be removed by that recovery.
- A repo/PR/SHA/phase operation claim fences different webhook deliveries
  across processes sharing the same SQLite database. The owning event lease
  renews it; expiration or termination releases it. An old lease cannot regain
  ownership or write after another worker reclaims the operation.
- A QA report commit waits for final-SHA CI and queues a new independent
  review. It cannot immediately enter human approval or dispatch release.
  Checkpoints allow the review-queue write to be replayed without rerunning QA.
- Identical report trees create no additional commits, avoiding an unnecessary
  cycle of HEAD invalidation and repeated review.
- Same-second handoffs use the GitHub comment ID to order evidence, so a newer
  failed outcome cannot be hidden behind an older success.
- Shared-lease `/claims/start` projects READY to RUNNING with ownership fencing,
  planned/applied audit, response-loss recovery, and live CI/Review checks for QA.
  It retains the execution lease and rejects stale retries after a requeue.
  This provides a controlled start interface; it does not migrate account workers
  or implement a repository-wide stale-RUNNING recovery controller.

Run the checked-in tests with `python -m pytest -q tests` in an isolated runtime
with the pinned test dependencies. All external workers and GitHub mutations
in process tests are mocked; tests do not invoke an API programmer or workflow.

## Remaining deployment and integration gates

These are requirements, not claims of implementation:

1. Account workers and Actions must use the same authoritative claim and lease
   store before changing labels or starting work. SQLite protections do not
   coordinate actors that never access that database, or independent databases.
   The authenticated API and client contract now exist in
   [shared-claim-protocol.md](shared-claim-protocol.md); live clients still need
   an authorized rollout and integration with that service.
2. New issue discovery, scheduled queue scanning and every machine-blocker type
   require live end-to-end acceptance. A labeled-PR event router alone does not
   establish reliable issue ingestion.
3. Multiple workflows still write labels. Read-before-write guards are not an
   atomic GitHub label CAS and cannot establish a unique global state writer.
   `/claims/advance` now computes verified transitions, serializes participating
   phase writers, retains audit records and resumes interrupted projections.
   Existing actors must adopt it before this requirement can be accepted.
4. The tested PR branch must pass independent review and an authorized rollout
   before its fixes become active on the default-branch workflow/server.
5. PR #78 at `da921abe5a413aca53af3193645108a66724c07a` was last observed with
   ordinary CI `action_required`, unresolved terminal policy and no final-SHA
   independent Review PASS. Re-fetch it before acting. Preserve its human-wait
   state unless a separate explicit owner action authorizes leaving it.

The branch CI can verify code regressions. It cannot by itself prove server
rollout, adoption by account workers, or successful recovery in GitHub.

## Discovery/client/restart batch

Implemented and wired into the service:
- Periodic paginated PR discovery feeding the existing native prototype/QA
  worker queue; durable scan identity and retry after temporary scan errors.
- Authenticated read-only account READY discovery and a cooperative account
  consumer using acquire/start/heartbeat/advance, with bounded acquisition retry.
- Native start-intent recovery before/after RUNNING label writes, and durable
  results even without report changes. Human wait still stops replay.
- In-process account-consumer -> real claim-router integration covering competing
  workers and verified Review -> QA transition. GitHub and agents are mocked.

Still not implemented/accepted globally:
- Issue ingestion into a planned PR and all machine-blocker lifecycles; a PR
  scanner does not cover these. Legacy RUNNING tasks without authoritative lease
  evidence are not automatically adopted.
- External worker publication across HEAD changes and adoption by actual account
  schedules/Actions. No account model or live client is started by these tests.
- A sole state writer across existing Actions/native workers/account workers.
- Authorized service rollout, independent review and live #78 final-SHA acceptance.

The branch can be reviewed and tested without modifying workflow YAML or
starting production. None of these tests authorizes rollout, merge or deployment.

Tracked external claims now have expiry CAS/recovery in the scanner. Without a
durable current-SHA result they requeue safely; with a result they reevaluate
advance gates without rerunning work. Tests cover old-worker fencing, one recovery
owner, response loss, pending/failed evidence, HEAD movement and human wait. This
requires workers to have adopted the shared service; it does not recover legacy
workers or claim that every blocker has an automatic resolution policy.
