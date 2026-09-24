# Prototype review — GH-ISSUE-77

## Decision

**Ready for implementation.** The task defines a finite terminal-policy enum, a
fail-closed default, a precise successful-QA wait state, and deterministic
acceptance cases. No product or data-model ambiguity prevents implementation.

## Scope and source

Reviewed the current-PR specification in `TASKS.md`, the Codex-to-OpenAI
Validator handoff, and the repository routing, handoff, reconciliation, and
watchdog design. The handoff is for `GH-ISSUE-77`, targets `workbuddy`, has
success status with no blockers, and its source SHA equals this PR head
(`f961dd8b026ef38dd1dd8087cd8a09acb67df3b5`).

This issue concerns task orchestration after QA. It does not introduce a job or
candidate matching prototype, occupation taxonomy, candidate data collection,
or a user-facing recruitment workflow. Those assumptions should not be added
to this implementation.

## Implementable behavior

1. Resolve the source task's policy as exactly one of `release_enabled`,
   `stop_after_qa`, or `owner_approval_required`.
2. Only `release_enabled` permits a successful, exact-current-SHA QA handoff to
   route to Codex release review.
3. `stop_after_qa` and `owner_approval_required` converge after successful QA
   to `status:review` plus `approval:production-required`. Remove active agent,
   phase, `status:todo`, and `status:running` labels. Preserve the successful
   QA handoff and its source SHA unchanged.
4. Missing, invalid, conflicting, or explicitly restrictive natural-language
   policy fails closed to the same owner-wait state. The review record must
   state the unresolved/conflicting value or instruction and what needs
   correction.
5. A later transition requires a separate explicit owner action. Replaying a
   successful QA event is not approval and must not add release labels or
   dispatch release/deployment.
6. A stale SHA, unsuccessful handoff, or non-empty blockers cannot advance the
   state. Duplicate events and reconciliation converge idempotently.

## Existing implementation gaps to address

The spec is clear, but the inspected implementation does not yet satisfy it:

- `orchestrator/task_router.py::next_labels` currently sends every successful
  QA result to `agent:codex + phase:release + status:todo`.
- `.github/workflows/openai-validator.yml` currently applies those release
  labels and dispatches `agent_codex_release` after QA success.
- `scripts/reconcile_handoff_state.py` currently has no QA-success transition
  and its state-label set does not include the owner-wait labels.
- The watchdog currently supervises active running labels. The new owner-wait
  state must remain outside running-worker timeout selection.

Implementation must update the label and dispatch paths together; changing
only the router or only the workflow would leave an unsafe release path.

## Required regression coverage

Cover the three valid enum values, absent and invalid values, contradictory
structured/natural-language policy, explicit restrictive instructions,
exact-SHA mismatch, non-success or blocked handoffs, owner-wait label cleanup,
replayed/duplicate QA events, no release/deployment dispatch while waiting,
and preservation of the successful QA handoff. The task specification already
names the minimum policy cases; these additional boundary cases follow directly
from its fail-closed and idempotency rules.

## Safety and privacy

Keep this transition deterministic and metadata-only. No candidate or employer
records, real payment execution, or production data are needed. An owner-wait
label must not be treated as authorization to merge, deploy, or access
production; normal CI and production gates remain in force.
