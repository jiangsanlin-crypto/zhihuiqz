# Classification validation — GH-ISSUE-77 QA

## Result

**Accepted.** This task classifies workflow terminal policy; it does not classify
occupations, skills, candidates, or jobs. Khmer taxonomy and aliases therefore
do not apply.

## Validated policy outcomes

| Source-task policy | Successful QA outcome | Release routing |
|---|---|---|
| `release_enabled`, without a restrictive instruction | Codex release review, subject to a successful exact-SHA handoff with no blockers | Allowed |
| `stop_after_qa` | Owner review | Not allowed |
| `owner_approval_required` | Owner review | Not allowed |
| Missing, unsupported, or conflicting value | Owner review with the policy reason recorded | Not allowed |
| Explicit restrictive instruction, including conflict with `release_enabled` | Owner review with the instruction recorded | Not allowed |

The accepted implementation resolves the source task's policy and fails closed
unless the effective value is `release_enabled`. Exact-SHA success and empty
blockers remain prerequisites. PR labels and replayed QA results cannot change
the source policy or grant owner approval.

`TASKS.md` sets `terminal_policy: owner_approval_required`, so this PR's
successful QA result must remain in owner review. The policy is control-flow
metadata, not a recruitment relevance score. No paid feature, candidate data,
or real production record participates in classification.
