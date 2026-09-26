# Synthetic Data Collection Plan — GH-ISSUE-46

## Collection objective

Collect the minimum non-secret control-plane evidence needed to decide
whether the repaired Codex-to-WorkBuddy path completed. This is not candidate
or employer data collection.

## Permitted fields

| Field | Example | Rule |
|---|---|---|
| task_id | `GH-ISSUE-46` | Required stable identifier |
| workflow | `Codex Product and Release` | Record workflow name only |
| action_run_id | `synthetic-run-46` | Synthetic or GitHub run identifier |
| model | `gpt-5.6-luna` | Must match the repository pin |
| effort | `max` | Must match the repository pin |
| step_result | `success` | Record per-step status |
| planning_pr | `synthetic-pr-46` | Record PR number or synthetic fixture |
| source_sha | `synthetic-sha-46` | Record only the revision identifier |
| handoff_status | `success` | Must have an empty blockers list |
| dispatch_event | `agent_workbuddy_prototype` | Must carry matching task/SHA |
| route_result | `success` | Route WorkBuddy Tasks accepted the event |
| retry_outcome | `completed` | Record outcome, never secret content |
| production_action | `skipped` | Must remain skipped for this task |

Do not collect API keys, payment-card details, billing-account identifiers,
real candidate profiles, real employer records, or request/response content
that contains personal data.

## Synthetic records

The control record may use `synthetic-run-46`, `synthetic-pr-46` and
`synthetic-sha-46`, together with the fictional recruitment records from
`docs/RECRUITMENT_RULES.md`. These values are fixtures only and must not be
sent to a production candidate store.

## Validation sequence

1. Resolve the approved runtime key and check only that it is non-empty; never
   print or persist its value.
2. Run the pinned Codex Action and verify its product-only file validation.
3. Verify the planning commit, automatic PR, labels and exact task marker.
4. Validate the `agent-handoff:v1` payload, including empty blockers and the
   current PR head SHA.
5. Verify the retry-enabled `agent_workbuddy_prototype` dispatch reaches Route
   WorkBuddy Tasks and that its task/SHA checks pass.
6. Classify any failure as `missing_secret`, `authentication_error`,
   `permission_error`, `dispatch_error`, `handoff_error`, `quota_error` or
   `other` without recording secret values.
7. Record only synthetic pass/fail evidence. Do not merge, deploy, execute a
   payment or onboard sensitive data.

The planning artifact is a test plan, not proof of a successful remote run.
