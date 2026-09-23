# Deployment

## Persistent Orchestrator stack

The persistent host runs only:
- Orchestrator;
- WorkBuddy runner.

Codex and ChatGPT run in GitHub Actions.

## Preferred bootstrap

After PR approval and merge to main:

1. create GitHub environment `orchestrator-production`;
2. require human approval on that environment;
3. configure the deployment secrets listed in
   `docs/DEPLOYMENT_HANDOFF.md`;
4. run `WorkBuddy Deploy Orchestrator`;
5. enter `DEPLOY-ORCHESTRATOR`.

The workflow uses SSH, checks out public `main`, writes the protected server
`.env`, runs Docker Compose, verifies `/readyz`, and rolls back to the
previous Git SHA if readiness fails.

## Server-side credentials

Only Orchestrator gets:
- GITHUB_REPOSITORY
- GITHUB_TOKEN
- ORCHESTRATOR_TOKEN

WorkBuddy runner gets:
- WORKBUDDY_TOKEN
- WorkBuddy OAuth values
- WORKBUDDY_MODEL=GLM-5.3-Flash
- WORKBUDDY_MODEL_LOCK_CONFIRMED=true after the dedicated app is verified

WorkBuddy receives no GitHub token.

## GitHub Actions secrets

Development/release:
- OPENAI_API_KEY
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN

Initial Orchestrator deployment:
- ORCH_SERVER_HOST
- ORCH_SERVER_USER
- ORCH_SERVER_PORT
- ORCH_SERVER_SSH_KEY
- ORCH_SERVER_KNOWN_HOSTS
- ORCH_SERVER_PATH
- ORCH_ENV_B64

## Main protection

Protect main:
- require PR;
- require CI;
- block force push;
- do not permit agent bypass.

Production approval remains human-only.
