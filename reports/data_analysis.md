# Data and policy analysis — GH-ISSUE-77

## Data required

The transition needs only task/PR metadata and a validated handoff:

| Field | Meaning | Handling |
|---|---|---|
| `task_id` | Correlates the source task, PR, and handoff | Must match exactly |
| Source terminal policy | Controls the successful-QA destination | Resolve to one allowed enum value; fail closed otherwise |
| Explicit source-task instruction | Can require a human wait despite a permissive structured value | An explicit stop, human-approval, or no-merge/deploy instruction takes precedence |
| Handoff `status` | QA result state | Advance only when `success` |
| Handoff `blockers` | Unresolved QA blockers | Must be empty to perform any successful transition |
| Handoff `source_sha` | Code revision accepted by QA | Must equal current PR head SHA; preserve the successful QA handoff unchanged |
| PR labels | Queue, active work, and owner-wait state | Canonicalize idempotently; remove active-route labels while waiting |

No candidate, employer, payment, or recruitment-profile data is needed.

## Policy semantics

The allowed values are exact identifiers:

- `release_enabled`: successful, exact-SHA, blocker-free QA may queue Codex
  release review.
- `stop_after_qa`: successful QA waits for the owner.
- `owner_approval_required`: successful QA waits for the owner.

Only `release_enabled` permits release routing. Missing, malformed, unsupported,
or conflicting values resolve to owner review and require a durable explanation
of the unresolved policy. Do not infer a permissive value from missing data or
coerce an unknown value. An explicit source-task instruction such as “stop
after QA,” “human approval required,” or “do not merge/deploy” overrides a
permissive structured value.

For this PR, `TASKS.md` supplies `terminal_policy: owner_approval_required`, so
the expected post-QA state is owner review. This is a control-flow decision, not
a score or recruitment classification.

## State transition contract

Owner wait is represented by `status:review` and
`approval:production-required`, with no agent, phase, `status:todo`, or
`status:running` route. It must not enqueue Codex release or dispatch release or
deployment. A later owner action is distinct from replaying the successful QA
event. The review record should identify the policy value or the conflicting
instruction and the explicit correction/owner action needed.

Retries, duplicate deliveries, and scheduled reconciliation must converge to
the same labels and must not create duplicate handoffs or dispatches. The
successful QA record remains authoritative at its exact tested SHA; a head-SHA
mismatch fails closed.

## Test-data guidance

Use synthetic task metadata for each valid value, missing/invalid values,
conflicts, and explicit natural-language instructions. Do not copy real issue
comments containing personal data into fixtures. Tests should assert policy
classification, canonical labels, absence of release/deploy actions in owner
wait, exact-SHA enforcement, and replay idempotency.
