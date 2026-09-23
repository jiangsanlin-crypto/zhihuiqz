# Synthetic Data Collection Plan — GH-ISSUE-43

## Collection objective

Collect the minimum non-secret control-plane evidence needed to decide whether
the Codex Action completed planning, created the PR, emitted a valid handoff
and triggered the WorkBuddy prototype route. This is not candidate or employer
data collection.

## Permitted fields

| Field | Synthetic example | Rule |
|---|---|---|
| `task_id` | `GH-ISSUE-43` | Required stable identifier |
| `workflow` | `Codex Product and Release` | Record workflow name only |
| `action_run_id` | `synthetic-run-43` | Synthetic or GitHub run identifier |
| `model` | `gpt-5.6-luna` | Must match the repository pin |
| `effort` | `max` | Must match the repository pin |
| `planning_result` | `success` | Record the Codex step result |
| `commit_sha` | `synthetic-planning-sha` | Record the planning revision only |
| `pr_number` | `synthetic-pr-43` | Record the created PR identifier |
| `pr_head_sha` | `synthetic-pr-head-sha` | Compare with handoff `source_sha` |
| `handoff_marker` | `agent-handoff:v1` | Must be present in the PR comment |
| `handoff_status` | `success` | Must have no blockers |
| `dispatch_event` | `agent_workbuddy_prototype` | Must match the route contract |
| `route_phase` | `prototype` | Must match the dispatch payload |
| `route_result` | `accepted` | Record route acceptance only |
| `production_action` | `skipped` | Must remain skipped for this task |

Record capability outcomes such as `pull_request_write=available` only as
booleans or categories. Never collect GitHub tokens, API keys, secret values,
payment-card data, real candidate profiles or real employer records.

## Validation sequence

1. Resolve the approved runtime secret and check only that it is non-empty;
   never print or persist its value.
2. Confirm the Action runs the pinned Codex model and effort with no fallback.
3. Confirm only the six planning files changed, then confirm the planning
   commit and automatic PR creation.
4. Read the PR head SHA and validate the handoff marker, JSON fields, task ID,
   success status, empty blockers and exact SHA equality.
5. Confirm the WorkBuddy labels and the
   `agent_workbuddy_prototype` payload are consistent with the PR.
6. Confirm `route-task.yml` accepts the synthetic event and relays it to the
   orchestrator. Record an acknowledgement or workflow result, not secret or
   personal data.
7. Confirm that merge and production deployment remain skipped.

Classify failures as `missing_secret`, `model_policy_error`,
`permission_error`, `planning_output_error`, `commit_or_pr_error`,
`handoff_error`, `dispatch_error`, `route_error` or `other`. Store the
category and step, not secret-bearing logs or request bodies.

The plan authorizes no production merge, deployment, payment or onboarding of
sensitive data. The planning artifact alone is not evidence that the remote
E2E has passed.
