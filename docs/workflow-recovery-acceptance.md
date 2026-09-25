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
4. The tested PR branch must pass independent review and an authorized rollout
   before its fixes become active on the default-branch workflow/server.
5. PR #78 at `da921abe5a413aca53af3193645108a66724c07a` was last observed with
   ordinary CI `action_required`, unresolved terminal policy and no final-SHA
   independent Review PASS. Re-fetch it before acting. Preserve its human-wait
   state unless a separate explicit owner action authorizes leaving it.

The branch CI can verify code regressions. It cannot by itself prove server
rollout, adoption by account workers, or successful recovery in GitHub.
