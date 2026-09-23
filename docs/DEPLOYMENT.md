# Deployment

## Persistent Orchestrator stack

The persistent host runs:
- Orchestrator;
- WorkBuddy runner.

Codex and ChatGPT run in GitHub Actions.

## One-time bootstrap

The initial Orchestrator bootstrap is an account/secret setup action. Configure
the server credentials and run WorkBuddy Deploy Orchestrator once.

The protected runtime bundle must contain the repository binding, runner token,
and the locked WorkBuddy model. WorkBuddy OAuth is optional for this bootstrap:
the stack may start in degraded mode while the OAuth application is unavailable.

After activation, normal product releases do not require per-release human
approval when the documented release gates and repository policy pass.

## Server-side credentials

Only Orchestrator gets:
- GITHUB_REPOSITORY
- GITHUB_TOKEN
- ORCHESTRATOR_TOKEN

WorkBuddy runner gets:
- WORKBUDDY_TOKEN
- optional WorkBuddy OAuth values for full cloud dispatch;
- WORKBUDDY_MODEL=GLM-5.3-Flash
- WORKBUDDY_MODEL_LOCK_CONFIRMED=true after verification

WorkBuddy itself receives no GitHub token. The Orchestrator performs validated
write-back/dispatch on its behalf.

## Degraded bootstrap mode

Degraded mode is an intentional, safe startup state for environments where
WorkBuddy OAuth cannot yet be created.

When OAuth is absent and the model lock is valid:

- /readyz returns HTTP 200 with ok=true, workbuddy_mode="degraded", and
  workbuddy_configured=false;
- the runner health endpoint remains observable, but real WorkBuddy cloud task
  dispatch is disabled;
- WorkBuddy /run returns HTTP 503 with an explicit degraded-mode reason;
- the Orchestrator records the phase as blocked, keeps the same phase labels,
  and does not publish an agent-handoff:v1 marker or dispatch another agent;
- the central watchdog may warn or block stale work, but never promotes a
  degraded dispatch to another phase.

The model policy remains mandatory in degraded mode. A model mismatch or an
unconfirmed WORKBUDDY_MODEL_LOCK_CONFIRMED still fails readiness.

### Upgrade path to full mode

1. Add a valid WorkBuddy access token, or the client ID, client secret, and
   refresh token, to the protected runtime bundle.
2. Restart/recreate the stack so the runner reloads the protected environment.
3. Confirm /readyz reports HTTP 200 with workbuddy_mode="full" and
   workbuddy_configured=true.
4. Retry the same blocked WorkBuddy phase. No handoff is inferred from the
   degraded attempt.

## GitHub Actions secrets

- OPENAI_API_KEY
- AGENT_GITHUB_TOKEN
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN
- REPO_ADMIN_TOKEN
- ORCH_SERVER_HOST
- ORCH_SERVER_USER
- ORCH_SERVER_PORT
- ORCH_SERVER_SSH_KEY
- ORCH_SERVER_KNOWN_HOSTS
- ORCH_SERVER_PATH
- ORCH_ENV_B64
- AUTO_PRODUCTION_ENABLED
- EMERGENCY_STOP

## Main protection

Main remains protected:
- PR required;
- required CI test context;
- admins follow protection;
- force push disabled;
- deletion disabled.

The normal full-auto policy requires zero human approving reviews so the
automation identity can merge only after deterministic gates/CI pass.

## Runtime release deployment

Codex release gate -> WorkBuddy deployment gate -> required CI -> automatic
merge -> server deployment -> 0/1/5/15 minute readiness checks -> rollback on
failure -> done.

Degraded bootstrap may start the service, but it cannot satisfy a WorkBuddy
phase or deployment gate until full mode is restored.
