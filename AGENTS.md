# Multi-Agent Workflow

The normal delivery pipeline has three logical AI work bodies plus one emergency
account-backed escalation worker.

## Canonical pipeline

```text
Codex / product planning (OpenAI API Luna)
        ↓
OpenAI Validator / prototype validation (OpenAI API Luna)
        ↓
ChatGPT / formal implementation (owner account Chat 5.6 Sol High)
        ↓
Work GPT-6 / code review + targeted repair
        ↓
OpenAI Validator / QA + UI/UX + classification acceptance
        ↓
Codex / release review + release notes
        ↓
OpenAI Validator / deployment readiness gate
        ↓
GitHub Actions / merge + deploy + health verification / rollback
        ↓
status:done
```

For handoff compatibility, OpenAI Validator keeps agent ID `workbuddy`.
This is not WorkBuddy Cloud and requires no WorkBuddy OAuth.

## Emergency escalation

The owner's ChatGPT Work GPT-6 worker is the emergency/high-difficulty
implementation path. It may take an implementation task when explicitly routed
for urgency, repeated CI failure, a blocked normal implementation, or a complex
recovery task. It must obey the same PR-branch, handoff, CI and production
boundaries as the normal ChatGPT implementation role.

The emergency worker does not authorize direct main writes, merge or deployment.

## Handoff rule

Every completed phase publishes `<!-- agent-handoff:v1 -->`.

A next phase may start only when:
- task ID matches;
- from/to logical agent matches;
- expected phase matches;
- previous handoff status is success;
- blockers are empty;
- handoff source SHA equals the current PR head SHA.

API-owned phases use GitHub Actions dispatch. Account Chat implementation is
queued by PR labels and consumed automatically by the account scheduled worker.
After Account Chat finishes, it queues `agent:workreview + phase:code-review`.
Work GPT-6 independently reviews the implementation, performs only targeted
repairs when necessary, verifies exact-final-SHA CI, then queues
`agent:workbuddy + phase:qa` with `status:todo` last. That final label event
starts OpenAI Validator QA.

## Model and execution policy

- Codex API coordinator: `gpt-6-luna` / high.
- OpenAI Validator API: `gpt-6-luna` / high.
- Primary programmer: owner account ChatGPT 5.6 Sol / High.
- Mandatory senior reviewer/repair engineer: owner account ChatGPT Work GPT-6.
- Emergency programmer: owner account ChatGPT Work GPT-6, subject to the model
  actually available/configured in Work.
- API Sol implementation worker: retired; normal workload must be zero.

OpenAI now exposes GPT-6 Luna and GPT-6 Sol in the API as `gpt-6-luna` and `gpt-6-sol`. API coordination/validation uses `gpt-6-luna` / high. The API Sol programmer remains retired because normal implementation is account-backed.

## Production policy

Automatic merge/deploy is allowed only when repository production controls,
required CI and all release/deployment gates succeed. No agent may bypass failed
gates or branch protection.

Real payment execution and real candidate production data require separate
explicit authorization.
