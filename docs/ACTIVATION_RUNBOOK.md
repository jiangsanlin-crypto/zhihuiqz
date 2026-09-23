# Full-Auto Activation Runbook

## One-time activation sequence

1. Configure `REPO_ADMIN_TOKEN`.
2. Run `Configure Main Protection` with `PROTECT-MAIN`.
3. Configure `AGENT_GITHUB_TOKEN`, `OPENAI_API_KEY`,
   `ORCHESTRATOR_TOKEN`, server secrets and `ORCH_ENV_B64`.
4. Configure `AUTO_PRODUCTION_ENABLED=true`.
5. Configure `EMERGENCY_STOP=false`.
6. Lock the dedicated WorkBuddy app to `GLM-5.3-Flash`.
7. Run `Activation Readiness -> predeploy`.
8. Bootstrap/deploy the persistent Orchestrator.
9. Run `Activation Readiness -> postdeploy`.
10. Run `Multi-Agent E2E Smoke`.
11. Start real work through `Start Agent Task`.

## Normal task flow after activation

```text
Start Agent Task
 -> Codex
 -> WorkBuddy
 -> ChatGPT
 -> WorkBuddy
 -> Codex
 -> WorkBuddy deployment gate
 -> wait required CI
 -> automatic PR merge
 -> automatic production deployment
 -> 0/1/5/15 minute health checks
 -> rollback on failure
 -> done
```

No normal-path human handoff is required.

## Required secrets

- `AGENT_GITHUB_TOKEN`
- `OPENAI_API_KEY`
- `ORCHESTRATOR_URL`
- `ORCHESTRATOR_TOKEN`
- `REPO_ADMIN_TOKEN`
- `ORCH_SERVER_HOST`
- `ORCH_SERVER_USER`
- `ORCH_SERVER_PORT`
- `ORCH_SERVER_SSH_KEY`
- `ORCH_SERVER_KNOWN_HOSTS`
- `ORCH_SERVER_PATH`
- `ORCH_ENV_B64`
- `AUTO_PRODUCTION_ENABLED`
- `EMERGENCY_STOP`

Do not commit or paste secret values into Issues/chat.

## Main protection

Main remains protected:
- PR required;
- CI `test` required and current;
- force push disabled;
- deletion disabled;
- admins also follow protection.

For full automation, no approving review or CODEOWNERS review is required on
normal product PRs. Merge still cannot occur until required CI/gates pass.

## Emergency behavior

Set `EMERGENCY_STOP=true` to stop automatic merge/deploy before production
execution.

A failed deployment automatically attempts rollback to the previous server SHA
and marks the task blocked.

## Sensitive business actions

This runbook automates software delivery. It does not grant permission to
execute real payments or process real candidate production data automatically.
