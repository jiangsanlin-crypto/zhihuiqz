# Deployment

## Persistent Orchestrator stack

The persistent host runs:
- Orchestrator;
- WorkBuddy runner.

Codex and ChatGPT run in GitHub Actions.

## One-time bootstrap

The initial Orchestrator bootstrap is an account/secret setup action. Configure
the server credentials and run `WorkBuddy Deploy Orchestrator` once.

After activation, normal product releases do not require per-release human
approval.

## Server-side credentials

Only Orchestrator gets:
- GITHUB_REPOSITORY
- GITHUB_TOKEN
- ORCHESTRATOR_TOKEN

WorkBuddy runner gets:
- WORKBUDDY_TOKEN
- WorkBuddy OAuth values
- WORKBUDDY_MODEL=GLM-5.3-Flash
- WORKBUDDY_MODEL_LOCK_CONFIRMED=true after verification

WorkBuddy itself receives no GitHub token. The Orchestrator performs validated
write-back/dispatch on its behalf.

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
- required CI `test` context;
- admins follow protection;
- force push disabled;
- deletion disabled.

The normal full-auto policy requires zero human approving reviews so the
automation identity can merge only after deterministic gates/CI pass.

## Runtime release deployment

Codex release gate -> WorkBuddy deployment gate -> required CI -> automatic
merge -> server deployment -> 0/1/5/15 minute readiness checks -> rollback on
failure -> done.
