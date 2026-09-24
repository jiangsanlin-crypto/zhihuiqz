# Policy classification validation — GH-ISSUE-77

## Classification domain

This task has no Khmer occupation or skill taxonomy. The relevant classification
is the source task's terminal policy, with these mutually exclusive outcomes:

| Resolved policy | Successful QA destination | Release allowed? |
|---|---|---|
| `release_enabled`, with no explicit restrictive instruction | Codex release review, subject to exact-SHA success and empty blockers | Yes |
| `stop_after_qa` | Owner wait | No |
| `owner_approval_required` | Owner wait | No |
| Missing, invalid, or conflicting policy | Owner wait with reason recorded | No |
| Explicit restrictive source-task instruction, including one that conflicts with `release_enabled` | Owner wait with instruction recorded | No |

The `release_enabled` result is valid only when the effective policy has no
conflict. An unknown value must never be silently normalized into that result.

## Classification rules

- Resolve policy from the source task, not from a replayed QA event or current
  PR labels.
- Treat recognized explicit restrictions as an override to structured
  permission.
- Preserve ambiguity as an owner-review reason instead of guessing.
- Apply the destination only after verifying task ID, successful handoff,
  empty blockers, and equality between handoff SHA and current PR head SHA.
- Reconciliation must recompute the same result and converge without emitting
  another release transition or dispatch.

## Acceptance observations

`TASKS.md` selects `owner_approval_required`; therefore this PR's policy class
is owner wait after QA success. The listed regression cases—release-enabled,
stop-after-QA, explicit owner approval, missing/ambiguous policy, and duplicate
or replayed success—are sufficient to distinguish the required outcomes.
Include structured/natural-language conflict and stale-SHA tests so the
fail-closed and exact-revision invariants are directly exercised.

No candidate/job relevance scores, paid employer features, or Khmer aliases
are involved. Do not introduce recruitment classifications into this state
machine.
