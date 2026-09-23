# Validation Agent Migration

WorkBuddy Cloud is no longer part of the active automation path.

The previous WorkBuddy responsibilities are now executed by an independent
OpenAI Validation Agent in GitHub Actions using the existing
`OPENAI_API_KEY`.

## Compatibility

To avoid breaking existing handoff validation, labels and historical PRs, the
internal agent ID remains:

`workbuddy`

This is only a compatibility identifier. It no longer means an external
WorkBuddy Cloud task.

## Runtime

- Model: `gpt-5.6-luna`
- Effort: `high`
- Transport: GitHub `repository_dispatch`
- Credentials: OpenAI API key only
- WorkBuddy OAuth: not required

## Phases

Prototype validation produces prototype/data/classification/UI reports plus
`reports/prototype_gate.json`.

QA produces test/UI/classification reports plus
`reports/qa_summary.json`.

Deployment review produces `reports/deployment_plan.md` and
`reports/deployment_gate.json`.

Only a ready machine-readable gate advances the workflow.
