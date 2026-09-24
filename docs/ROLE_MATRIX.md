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

## Work GPT-6 senior reviewer and repair engineer

Owns mandatory independent review of every normal implementation before Luna QA.
Reviews correctness, regressions, edge cases, tests, security/privacy,
idempotency/concurrency where relevant, and task-scope compliance.

Runtime: owner's ChatGPT Work GPT-6 configuration.

Logical handoff ID: `workreview`.

If no material defect exists, it must not churn code. If a clear defect is
found, it repairs the same PR head branch with the smallest safe change and
requires exact-final-SHA CI success before handoff.

## OpenAI Validation Agent

Owns independent prototype validation, data-assumption review, classification
validation, deterministic QA, multilingual UI/UX acceptance and
deployment-readiness review.

Runtime: OpenAI API `gpt-6-luna` / high.

Compatibility handoff ID: `workbuddy`. It does not use WorkBuddy Cloud or
WorkBuddy OAuth.

## Emergency Work engineer

The same Work GPT-6 execution surface also owns explicitly escalated
urgent/high-difficulty implementation or recovery tasks.

Because the current account-event runtime may not expose a trusted
machine-readable model identity, execution success and model-identity
verification must remain separate claims.

After emergency implementation, the resulting code still passes through the
Work code-review gate before Luna QA.

## Automation control plane

GitHub Actions performs API-agent routing, handoff validation, deterministic
test gates, merge, deployment, health checks and rollback. Account tasks handle
the implementation execution surface without repository OPENAI_API_KEY usage.
