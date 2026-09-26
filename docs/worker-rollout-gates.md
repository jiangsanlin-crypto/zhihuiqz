# Worker rollout and live acceptance gates for #80

## Current pre-deployment state

PR #83 now contains the shared claim/state authority, workflow wake bridge,
planner/validator dispatch, account-worker broker, exact-SHA publication fencing,
timeout/recovery logic, and a synthetic E2E that terminates at Human Approval.
Repository CI validates the Python test suite, policy checks, workflow YAML and
Docker Compose.

The account workers are migrated by configuration to the broker protocol
documented in account-worker-shared-protocol.md. They must not write workflow
labels directly. Until PR #83 is merged and the shared controller is deployed
from the reviewed main SHA, those workers fail closed rather than falling back
to legacy label mutation.

## Activation sequence

1. Merge the independently reviewed PR #83 exact HEAD into main.
2. Let Deploy Shared Control Runtime deploy that exact main SHA. Readiness must
   report shared-claims:v1, the expected repository/build SHA,
   writes_enabled=true, and agents_enabled=false.
3. Keep CONTROL_WORKFLOW_MODE empty or shared; shared mode is the fail-closed
   default. Legacy mode is an explicit rollback only.
4. Verify both account workers can use the owner-comment broker. They acquire,
   start, heartbeat, publish via prepare/confirm, and advance only through the
   controller.
5. Run Shared Full-Auto E2E. It must create one synthetic Issue, one linked PR,
   traverse planner -> prototype -> implementation -> independent Review -> QA ->
   final-SHA independent Review -> evidence-only QA, and stop at canonical Human
   Approval without merge or production deployment.

## Acceptance evidence

Acceptance requires all of the following on the synthetic task:

- one durable planning publication and no duplicate PR;
- one live lease per phase and a rejected concurrent contender;
- exact-SHA ordinary CI before every evidence-dependent transition;
- account implementation and independent Review claims through the broker;
- two-phase direct-child branch publication with no force-push;
- stale old-SHA CI/review/QA rejected after any HEAD change;
- repair routed through escalation-repair and then a new independent Review;
- QA report commits re-reviewed on their new exact SHA;
- final QA produces status:review + approval:production-required with no active
  agent/phase/todo/running/blocked label;
- no automatic merge, release or production deployment.

A controller deployment failure must roll back and leave writes disabled. A
worker that cannot reach or authenticate to the controller must stop; it must not
resume legacy direct label writes.

## Human boundary

Human Approval is the intentional terminal state of the machine workflow.
Approval, merge, release and production deployment remain explicit owner actions.
