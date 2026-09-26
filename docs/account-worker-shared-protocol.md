# Account worker shared-control protocol

This protocol is the only supported state-transition path for the owner-account
Chat implementation worker and Work independent-review/repair worker.

The account worker may read GitHub, review code, create unpublished Git objects,
fast-forward the already-authorized PR head, run or observe tests, and publish
trusted evidence comments. It must **not** write workflow labels directly.

## Control request transport

State and lease operations are requested by an owner-authored PR comment:

~~~text
<!-- shared-control-request:v1 -->
~~~json
{
  "action": "acquire",
  "phase": "phase:implementation",
  "worker_id": "account-chat-sol",
  "request_id": "impl:GH-ISSUE-123:<sha>:<attempt>"
}
~~~
~~~

The broker replies on the same PR with:

~~~text
<!-- shared-control-result:v1 -->
~~~json
{
  "status": "granted",
  "action": "acquire",
  "delivery_id": "...",
  "lease_id": "...",
  "worker_id": "...",
  "source_sha": "...",
  "lease_expires_at": "..."
}
~~~
~~~

Every later request carries delivery_id, lease_id and worker_id.
Supported actions are heartbeat, prepare_head, confirm_head, advance, release,
and decision.

A worker must wait for the matching result comment before continuing. A rejected,
missing, stale or ambiguous receipt is a hard stop. The worker never repairs a
control failure by changing labels itself.

## Exact-SHA branch publication

Implementation and escalation-repair may publish code. A branch update is a
two-phase operation:

1. Re-read the open PR and exact current HEAD.
2. Create blobs, a tree and a direct-child commit with Git Data APIs without
   moving the branch ref.
3. Request prepare_head with target_sha equal to the new commit.
4. Wait for a successful broker receipt.
5. Fast-forward the existing PR branch with force=false.
6. Request confirm_head.
7. Wait for a successful receipt; its source_sha becomes the owned exact SHA.

Never use Contents API writes for owned code publication because they move the
branch before prepare_head. Never force-push. Re-run the protocol for each
subsequent repair commit.

## Implementation worker

For agent:chatgpt + phase:implementation + status:todo, acquire through the
broker, publish an owner-authored agent-claim:v1 exact-SHA claim record, and
heartbeat during substantial work. The start gate independently verifies the
prototype handoff and ordinary current-SHA CI.

After implementation, publish code through the two-phase protocol, wait for
ordinary pull-request CI on the exact final SHA, then publish one trusted
agent-handoff:v1 from chatgpt to workreview, phase implementation,
status=success, blockers=[], exact source_sha and PR number. Request advance;
only the controller projects the next labels.

Transient work may request decision=retry. After bounded implementation repair
is exhausted, request decision=repair with a stable reason code; the controller
routes to Work escalation-repair. Human/product/secret/permission/security/
privacy/non-repository blockers request decision=block.

## Independent Review / repair worker

For agent:workreview + phase:code-review + status:todo, acquire through the
broker, publish an owner-authored exact-SHA agent-claim:v1, and perform an
independent review. A PASS requires exact-current-SHA ordinary CI and a material
review, not CI alone. Publish one agent-handoff:v1 from workreview to workbuddy,
phase code_review, with an independent_code_review=passed check, then request
advance.

A review that finds a repository-fixable defect requests decision=repair; do not
edit code while holding the code-review lease. The controller moves the task to
phase:escalation-repair. Acquire a new repair lease, publish fixes only through
the two-phase branch protocol, publish an owner-authored agent-repair:v1 record
for the exact repaired SHA with status=waiting_exact_sha_ci, wait for exact-SHA
CI, then request advance. That routes back to a new independent code-review
execution; repair never self-approves.

After QA writes report files, the controller intentionally routes the new final
SHA back through independent Review. The subsequent QA pass is evidence-only and
converges to status:review + approval:production-required.

## Terminal and recovery invariants

Human Approval has no active agent/phase and is never exited automatically.
Unknown or human blockers stay blocked. Lease loss, concurrent HEAD movement,
unexpected labels, stale evidence, failed/pending current-SHA CI, or a broker
failure all fail closed. Recovery, timeout handling and state convergence are
owned by the shared controller, not by account-worker prompt logic.
