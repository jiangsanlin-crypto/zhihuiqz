# zhihuiqz · Three-Agent GitHub Orchestrator

This repository coordinates exactly three AI work bodies:

```text
Codex / product planning
  -> WorkBuddy / prototype + data + classification validation
  -> ChatGPT / implementation
  -> WorkBuddy / QA + UI/UX + classification acceptance
  -> Codex / release review
  -> Human / merge + production approval
  -> WorkBuddy / approved deployment
```

The same task ID follows the work through every phase. Each phase publishes a
structured `agent-handoff:v1` record containing the next owner, model,
artifacts, checks, blockers, source SHA and acceptance criteria.

## Strict models

- ChatGPT development: `gpt-6-sol`, effort `high`
- Codex product/release: `gpt-6-luna`, effort `max`
- WorkBuddy: `GLM-5.3-Flash`, locked in the dedicated WorkBuddy app

See `docs/MODEL_POLICY.md`.

## Monitoring

Primary handoff is real-time/event-driven through GitHub Actions and the
Orchestrator webhook. Agents do not individually poll GitHub.

A central watchdog runs every 10 minutes only to detect lost/stuck handoffs, with separate running limits for Codex (55m), WorkBuddy (30m), and ChatGPT (75m).

## Persistent Orchestrator

After human merge to main, use:

`Actions -> WorkBuddy Deploy Orchestrator`

This deploys the Orchestrator to the configured persistent Linux server,
requires the protected `orchestrator-production` environment, checks
`/readyz`, and rolls back to the previous Git SHA if readiness fails.

See:
- docs/ROLE_MATRIX.md
- docs/HANDOFF_PROTOCOL.md
- docs/MODEL_POLICY.md
- docs/DEPLOYMENT_HANDOFF.md
- docs/ACTIVATION_RUNBOOK.md
