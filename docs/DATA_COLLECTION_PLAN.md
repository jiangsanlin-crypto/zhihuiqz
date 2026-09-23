# Synthetic Data Collection Plan — GH-ISSUE-42

## Collection objective

Collect the minimum non-secret control-plane evidence needed to decide whether
the Codex product-planning Action reached OpenAI and completed successfully
after billing activation. This is not candidate or employer data collection.

## Permitted fields

| Field | Example | Rule |
|---|---|---|
| task_id | `GH-ISSUE-42` | Required stable identifier |
| workflow | `Codex Product and Release` | Record workflow name only |
| action_run_id | `synthetic-run-42` | Synthetic or GitHub run identifier |
| model | `gpt-5.6-luna` | Must match the repository pin |
| effort | `max` | Must match the repository pin |
| step_result | `success` | Record per-step status |
| error_class | `none` | Use a category, never a secret or token |
| handoff_source_sha | `synthetic-sha` | Record only the source revision |
| production_action | `skipped` | Must remain skipped for this task |

Do not collect API keys, payment-card details, billing-account identifiers,
real candidate profiles, real employer records, or request/response content
that contains personal data.

## Synthetic records

The control record may use `synthetic-run-42` and the fictional recruitment
records from `docs/RECRUITMENT_RULES.md`. These values are fixtures only and
must not be sent to a production candidate store.

## Validation sequence

1. Resolve the key through the approved Action secret path and check only that
   it is non-empty.
2. Run the pinned Codex Action.
3. Classify any failure as `missing_secret`, `billing_or_account_error`,
   `authentication_error`, `quota_error`, `handoff_error` or `other` without
   recording secret values.
4. Check the product-only allowlist and task/SHA handoff fields.
5. Retain the pass/fail summary as synthetic CI evidence.

No collection step authorizes a production merge, deployment, payment or
onboarding of sensitive data.
