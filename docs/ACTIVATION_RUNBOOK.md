# Three-Agent Activation Runbook

## Current activation sequence

1. Configure `REPO_ADMIN_TOKEN`.
2. Run `Configure Main Protection` with `PROTECT-MAIN`.
3. Configure the protected `orchestrator-production` environment.
4. Configure `AGENT_GITHUB_TOKEN`, `OPENAI_API_KEY`,
   `ORCHESTRATOR_TOKEN`, deployment secrets and `ORCH_ENV_B64`.
5. Lock the dedicated WorkBuddy app to `GLM-5.3-Flash`.
6. Run `Activation Readiness` with stage `predeploy`.
7. Run `WorkBuddy Deploy Orchestrator` with `DEPLOY-ORCHESTRATOR`.
8. Run `Activation Readiness` with stage `postdeploy`.
9. Run `Multi-Agent E2E Smoke` with `RUN-E2E`.
10. Inspect the final human-review state.
11. Start real work through `Start Agent Task`.

## Required GitHub secrets

Automation:
- `AGENT_GITHUB_TOKEN`
- `OPENAI_API_KEY`
- `ORCHESTRATOR_URL`
- `ORCHESTRATOR_TOKEN`

Repository administration:
- `REPO_ADMIN_TOKEN`

Persistent Orchestrator deployment:
- `ORCH_SERVER_HOST`
- `ORCH_SERVER_USER`
- `ORCH_SERVER_PORT`
- `ORCH_SERVER_SSH_KEY`
- `ORCH_SERVER_KNOWN_HOSTS`
- `ORCH_SERVER_PATH`
- `ORCH_ENV_B64`

Do not commit or post any secret value in an Issue.

## Automation identity

`AGENT_GITHUB_TOKEN` must be a separate, narrowly scoped identity with only
the repository permissions needed for:
- task branch pushes;
- Issue/PR comments and labels;
- pull-request updates;
- `repository_dispatch`.

It must not have main-branch protection bypass.

`REPO_ADMIN_TOKEN` is a separate administrative identity used only for
repository-protection setup/verification. The readiness gate fails if the two
tokens are identical.

## WorkBuddy model lock

Before predeploy readiness:
1. expose only `GLM-5.3-Flash` in the dedicated WorkBuddy/Buddy App;
2. make it the default;
3. disable Auto/alternate models for that integration;
4. set `WORKBUDDY_MODEL=GLM-5.3-Flash` in the protected server env;
5. set `WORKBUDDY_MODEL_LOCK_CONFIRMED=true` only after the UI/model
   configuration has been verified.

## Server env validation

`Activation Readiness` decodes `ORCH_ENV_B64` into an ephemeral runner file
and validates only required keys and consistency. It does not print secret
values.

It checks:
- repository identity;
- Orchestrator bearer-token consistency;
- WorkBuddy model lock;
- WorkBuddy OAuth/access-token completeness.

## Real-time handoff chain

```text
Codex product planning
  -> repository_dispatch
WorkBuddy prototype validation
  -> repository_dispatch
ChatGPT implementation
  -> repository_dispatch
WorkBuddy QA
  -> repository_dispatch
Codex release review
  -> Human approval
```

Labels are visible state/safety gates. They are not relied upon as the sole
cross-workflow transport.

## Monitoring

Primary routing is real time.

The recovery watchdog runs every 10 minutes:
- queued handoff >10 minutes -> one warning;
- Codex running >55 minutes -> blocked;
- WorkBuddy running >30 minutes -> blocked;
- ChatGPT running >75 minutes -> blocked.

## Starting normal work

After E2E passes, use:

`Actions -> Start Agent Task`

Provide:
- task title;
- objective/acceptance requirements;
- priority.

The launcher creates the source Issue, applies
`phase:product-plan + status:todo`, then applies `agent:codex` last. This
starts the automatic chain without requiring manual handoff between AI work
bodies.

## Failure rule

Never skip a blocked phase. Fix the blocker and retry the same phase through its
manual workflow-dispatch entry point.
