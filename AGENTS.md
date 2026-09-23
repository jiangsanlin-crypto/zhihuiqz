# Multi-Agent Workflow

Exactly three AI work bodies participate.

## Canonical pipeline

```text
Codex / product planning
        ↓
WorkBuddy / prototype + data + classification validation
        ↓
ChatGPT / formal implementation
        ↓
WorkBuddy / tests + UI/UX + classification acceptance
        ↓
Codex / release review + release notes
        ↓
WorkBuddy / deployment readiness gate
        ↓
GitHub Actions / automatic merge + production deploy
        ↓
WorkBuddy-owned health checks / rollback
        ↓
status:done
```

## Handoff rule

Every phase publishes `<!-- agent-handoff:v1 -->`.

A phase may start only when:
- task ID matches;
- from/to agent matches;
- expected phase matches;
- previous handoff status is success;
- blockers are empty;
- handoff source SHA equals the current PR head SHA.

Cross-workflow execution uses explicit `repository_dispatch`. Labels are
visible state/safety gates, not the sole transport.

## Model policy

- ChatGPT: `gpt-5.6-sol` / high
- Codex: `gpt-5.6-luna` / max
- WorkBuddy: `GLM-5.3-Flash`

No fallback is allowed.

## Production policy

Normal software delivery is fully automatic after one-time activation.

Automatic merge/deploy is allowed only when:
- `AUTO_PRODUCTION_ENABLED=true`;
- `EMERGENCY_STOP` is not true;
- required CI passes;
- Codex release gate is ready;
- WorkBuddy deployment gate is ready.

No agent may bypass failed gates or branch protection.

Real payment execution and real candidate production data still require
separate explicit authorization; this full-auto policy covers software delivery,
not business transactions or sensitive-data onboarding.
