# Full-Auto Activation Runbook

## One-time activation sequence

1. Configure repository secrets:
   - ORCH_SERVER_HOST
   - ORCH_SERVER_USER
   - ORCH_SERVER_SSH_KEY
   - ORCH_SERVER_KNOWN_HOSTS
   - ORCH_ENV_B64
   - optional ORCH_SERVER_PORT / ORCH_SERVER_PATH
   - optional ORCHESTRATOR_URL
2. Ensure ORCH_ENV_B64 contains:
   - GITHUB_TOKEN
   - GITHUB_REPOSITORY=jiangsanlin-crypto/zhihuiqz
   - ORCHESTRATOR_TOKEN
   - WORKBUDDY_TOKEN
   - WORKBUDDY_MODEL=GLM-5.3-Flash
   - WORKBUDDY_MODEL_LOCK_CONFIRMED=true
   - either WORKBUDDY_ACCESS_TOKEN or the WorkBuddy OAuth refresh credentials
   - OPENAI_API_KEY, unless OPENAI_API_KEY is configured separately as a repository secret
3. Run Activation Readiness -> predeploy.
4. Run WorkBuddy Deploy Orchestrator -> DEPLOY-ORCHESTRATOR.
5. Run Activation Readiness -> postdeploy.
6. Run Multi-Agent E2E Smoke -> RUN-E2E.
7. Start normal work through Start Agent Task.

## GitHub automation identity

Normal GitHub Actions use the built-in `github.token`. Cross-workflow chaining
uses `repository_dispatch`, which is the explicit transport for agent-to-agent
handoffs.

A separate AGENT_GITHUB_TOKEN is no longer required.

## Production policy

The repository-controlled file `config/automation_policy.json` is authoritative.

Current policy:
- auto production enabled;
- emergency stop inactive;
- CI check `test` required;
- synthetic E2E tasks never perform real production deployment.

To stop production automation, change `emergency_stop` to `true` in a
reviewed repository change.

## Main protection

Branch protection is recommended as defense in depth, but the runtime chain does
not depend on an administration token. The production workflow independently
requires the CI `test` check, release gate and WorkBuddy deployment gate before
merge.

## Normal task flow

```text
Start Agent Task
 -> Codex
 -> WorkBuddy
 -> ChatGPT
 -> WorkBuddy
 -> Codex
 -> WorkBuddy deployment gate
 -> CI test
 -> automatic PR merge
 -> automatic production deployment
 -> 0/1/5/15 minute health checks
 -> rollback on failure
 -> done
```

## Sensitive business actions

This runbook automates software delivery only. It does not authorize real
payment execution or processing of real candidate production data.
