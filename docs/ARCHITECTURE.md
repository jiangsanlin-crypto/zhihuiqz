# Architecture

```text
GitHub Issue
  |
  | agent:codex + phase:product-plan
  v
Codex API coordinator
gpt-6-luna / high
  |
  | product documents + handoff
  v
OpenAI Validator
gpt-6-luna / high
prototype/data/classification validation
  |
  | agent:chatgpt + phase:implementation + status:todo
  v
Owner account ChatGPT worker
GPT-5.6 Sol / High
  |
  | code/tests + implementation handoff
  | add agent:workreview + phase:code-review + status:todo(last)
  v
Owner account Work GPT-6
independent code review + targeted repair
  |
  | exact-final-SHA CI + code-review handoff
  | add agent:workbuddy + phase:qa + status:todo(last)
  v
OpenAI Validator
QA/UIUX/classification acceptance
  |
  v
Codex API coordinator
release review + release notes
  |
  v
OpenAI Validator
deployment readiness
  |
  v
GitHub Actions
required CI -> merge -> deploy -> health checks / rollback
```

## Emergency path

The owner's ChatGPT Work GPT-6 worker is now a mandatory independent code-review
gate after normal implementation, and also remains the escalation path for
urgent/high-difficulty implementation or recovery.

Review is mandatory; code modification is conditional. When no material defect
is found, the reviewer must not churn code. When a clear in-scope defect is
found, it performs the smallest safe repair on the same PR head branch and
revalidates exact-final-SHA CI before Luna QA.

## Trust boundaries

- Codex and OpenAI Validator use OpenAI API Luna only.
- Normal implementation uses the owner's ChatGPT account and does not use the
  repository OPENAI_API_KEY.
- `.github/workflows/chatgpt-dev.yml` is a retired non-executing compatibility
  stub.
- Implementation workers may edit only the current task PR branch.
- Product/release and validation phases keep file allowlists.
- Main merge/deployment is performed only by deterministic GitHub Actions after
  required gates and CI.

## Routing

- API-to-API handoffs use explicit `repository_dispatch`.
- Validator prototype success queues implementation through PR labels; it never
  dispatches the retired API Sol worker.
- The account Chat scheduled worker consumes the queue automatically.
- Account Chat completion relabels the PR for Work code review.
- The Work review queue consumes `agent:workreview + phase:code-review`.
- Work completion relabels the PR for QA; `pull_request:labeled` then starts
  OpenAI Validator QA.
- The central watchdog is recovery-only.

## API model constraint

The repository pins the officially supported API model `gpt-6-luna` / high for Codex coordination and OpenAI Validator work. `gpt-6-sol` is available in the API, but the API Sol programmer remains retired so normal implementation workload stays at zero.
