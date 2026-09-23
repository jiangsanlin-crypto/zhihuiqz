# zhihuiqz · Three-Agent GitHub Orchestrator

The repository coordinates a fully automatic software-delivery chain:

```text
Codex product planning
  -> WorkBuddy prototype/data/classification validation
  -> ChatGPT implementation
  -> WorkBuddy QA/UIUX/classification acceptance
  -> Codex release review
  -> WorkBuddy deployment gate
  -> CI test
  -> automatic PR merge
  -> automatic production deployment
  -> 0m / 1m / 5m / 15m health verification
  -> rollback on failure
  -> done
```

## Models

- ChatGPT development: `gpt-5.6-sol` / high
- Codex product/release: `gpt-5.6-luna` / max
- WorkBuddy: `GLM-5.3-Flash`

No fallback is allowed.

## Dispatch

Agent handoffs use explicit `repository_dispatch`. GitHub Actions use the
built-in `github.token`; a separate AGENT_GITHUB_TOKEN is not required.

WorkBuddy is invoked by the persistent Orchestrator. The Orchestrator bearer
token is read from the protected runtime bundle.

## Production policy

`config/automation_policy.json` controls:
- whether automatic production is enabled;
- emergency stop;
- the mandatory CI check.

A production deployment also requires both Codex release gate and WorkBuddy
deployment gate to be ready.

## Activation

Required external configuration is intentionally narrow:
- persistent-server SSH secrets;
- ORCH_ENV_B64 runtime bundle;
- OpenAI API key;
- WorkBuddy token/OAuth.

Run Activation Readiness before and after deploying the persistent Orchestrator,
then run the synthetic E2E.

## Monitoring

Normal routing is real time. A central watchdog runs every 10 minutes only as a
recovery layer for lost/stuck work.
