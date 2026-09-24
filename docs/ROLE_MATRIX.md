# AI Work-Body Responsibility Matrix

## Codex API coordinator

Owns product management, recruitment rules, taxonomy, collection planning,
acceptance criteria, release review and release notes.

Runtime: OpenAI API `gpt-6-luna` / high.

## Account ChatGPT primary engineer

Owns frontend/backend implementation, classification engineering, APIs/data,
migrations, tests, PR-branch implementation and CI repair.

Runtime: owner's ordinary ChatGPT account, GPT-5.6 Sol / High.

Logical handoff ID: `chatgpt`.

The API-backed Sol implementation workflow is retired and carries zero normal
implementation workload.

## OpenAI Validation Agent

Owns independent prototype validation, data-assumption review, classification
validation, deterministic QA, multilingual UI/UX acceptance and
deployment-readiness review.

Runtime: OpenAI API `gpt-6-luna` / high.

Compatibility handoff ID: `workbuddy`. It does not use WorkBuddy Cloud or
WorkBuddy OAuth.

## Emergency Work engineer

Owns explicitly escalated urgent/high-difficulty implementation or recovery
tasks.

Runtime: owner's ChatGPT Work GPT-6 configuration. Because the current
account-event runtime does not expose a trusted machine-readable model identity,
tests must distinguish execution success from model-identity verification.

When it substitutes for implementation it publishes the logical
`chatgpt -> workbuddy` implementation handoff and returns to the same QA gate.

## Automation control plane

GitHub Actions performs API-agent routing, handoff validation, deterministic
test gates, merge, deployment, health checks and rollback. Account tasks handle
the implementation execution surface without repository OPENAI_API_KEY usage.
