# Repository Administration Setup

## Required setup

Normal full-auto operation no longer requires a separate repository-admin token
or a separate agent PAT.

GitHub Actions use the built-in `github.token` and explicit
`repository_dispatch` events.

Required repository secrets are limited to the persistent-server connection and
the protected runtime bundle:
- ORCH_SERVER_HOST
- ORCH_SERVER_USER
- ORCH_SERVER_SSH_KEY
- ORCH_SERVER_KNOWN_HOSTS
- ORCH_ENV_B64

Optional:
- ORCH_SERVER_PORT
- ORCH_SERVER_PATH
- ORCHESTRATOR_URL
- OPENAI_API_KEY if it is not included inside ORCH_ENV_B64

## Runtime bundle

ORCH_ENV_B64 is the base64-encoded server .env and is the single source for:
- server GitHub write token;
- Orchestrator bearer token;
- WorkBuddy runner token;
- WorkBuddy model lock;
- WorkBuddy OAuth/access token;
- optionally the OpenAI API key.

## Production control

`config/automation_policy.json` controls automatic production and emergency
stop state.

Branch protection remains recommended but is not an activation blocker because
the automatic deploy workflow directly verifies the CI test check and both
release gates before merging.

## WorkBuddy

The dedicated WorkBuddy app must expose only GLM-5.3-Flash before
WORKBUDDY_MODEL_LOCK_CONFIRMED=true is placed in the protected runtime bundle.
