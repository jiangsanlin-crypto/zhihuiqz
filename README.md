# zhihuiqz · Three-Agent GitHub Orchestrator

This repository coordinates a fully automatic software-delivery chain:

```text
Codex / product planning
  -> WorkBuddy / prototype + data + classification validation
  -> ChatGPT / implementation
  -> WorkBuddy / QA + UI/UX + classification acceptance
  -> Codex / release review
  -> WorkBuddy / deployment gate
  -> automatic PR merge
  -> automatic production deployment
  -> 0m / 1m / 5m / 15m health verification
  -> rollback on failure
  -> done
```

The same task ID follows the work through every phase. Each phase publishes a
structured `agent-handoff:v1` record containing the next owner, model,
artifacts, checks, blockers, source SHA and acceptance criteria.

## Strict models

- ChatGPT development: `gpt-5.6-sol`, effort `high`
- Codex product/release: `gpt-5.6-luna`, effort `max`
- WorkBuddy: `GLM-5.3-Flash`, locked in the dedicated WorkBuddy app

No model fallback is allowed.

## Automatic production controls

Full automatic merge/deploy is enabled only when:

- `AUTO_PRODUCTION_ENABLED=true`
- `EMERGENCY_STOP` is not `true`
- release gate = ready
- WorkBuddy deployment gate = ready
- required CI checks pass
- main branch protection is active
- Orchestrator is healthy

Any failed gate blocks the chain. A deployment failure triggers rollback to the
previous server Git SHA.

Real payment execution and use of real candidate production data remain outside
this automatic software-delivery permission unless separately authorized.

## Monitoring

Primary handoff is real-time/event-driven through `repository_dispatch`.
Agents do not individually poll GitHub.

A central watchdog runs every 10 minutes to detect lost/stuck handoffs.

## Activation

Use `Activation Readiness` before and after the first persistent Orchestrator
deployment. Once activated, start normal work through `Start Agent Task`.
