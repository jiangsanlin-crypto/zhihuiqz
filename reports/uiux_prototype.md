# UI/UX prototype review — GH-ISSUE-77

## User-facing state

The affected interface is the GitHub PR workflow, not the recruitment
platform's candidate or employer interface. After successful QA for the current
`owner_approval_required` policy, show the PR in the canonical owner-wait state:

- `status:review`
- `approval:production-required`
- no active agent, phase, `status:todo`, or `status:running` label

Add a concise review record that says QA succeeded at the recorded source SHA,
why the task is waiting, and what explicit owner action is needed to continue.
For an invalid or conflicting policy, name the value/instruction that caused
the wait and what must be corrected. Avoid implying that a successful QA result
has approved release, merge, deployment, payment execution, or production-data
access.

## Retry and replay experience

Repeated QA events should leave the same owner-wait labels and review record;
they must not create a duplicate handoff, wake Codex, or enqueue release or
deployment. A SHA mismatch or blocked handoff must not display a success-based
owner approval state; it remains blocked for repair/review according to the
existing failure path.

## Language and accessibility

This task changes orchestration metadata only. It adds no Khmer, English, or
Chinese recruitment UI, labels for job seekers, or employer-facing controls, so
multilingual recruitment assumptions are not applicable. Keep the PR review
record plain and explicit for the repository's owner; do not represent
`approval:production-required` as a generic translation of permission to
deploy.

## Privacy and fixtures

The interface can be validated with synthetic policy examples. It needs no
candidate data or personal details from real task comments. Keep review text to
the policy reason, QA SHA, and required owner action.
