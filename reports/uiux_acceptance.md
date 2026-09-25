# UI/UX acceptance — GH-ISSUE-77

## Result

**Accepted for the stated scope.** This change affects the GitHub PR workflow
and its review metadata, not job-seeker or employer product screens.

## Accepted owner-wait experience

For the task's `owner_approval_required` policy, successful QA leads to
`status:review` and `approval:production-required`, with active worker and
phase labels removed. A terminal-policy review comment records the task ID,
tested SHA, policy, and reason. The state makes clear that QA succeeded while
release still requires owner action.

Missing, invalid, conflicting, or explicitly restrictive policy also fails
closed to owner review with a reason. Replayed QA events do not turn that state
into release approval. Stale or blocked handoffs cannot present as accepted QA.

## Language, accessibility, and privacy

Khmer, English, and Chinese recruitment UI review is not applicable because no
recruitment UI or user-facing language content changes. The PR record uses
plain policy identifiers and an explicit owner-wait label; it does not imply
permission to merge, deploy, execute payments, or access production data.
Synthetic policy metadata is sufficient for these states, with no personal or
candidate data required.
