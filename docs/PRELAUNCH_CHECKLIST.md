# Production pre-launch checklist

This checklist is the final gate for the three-agent recruitment platform. It separates checks that can run in GitHub Actions from actions that require the repository owner or real infrastructure.

## Current repository baseline

As of 2026-09-23:

- PR #1 is already merged; it is not an outstanding approval gate.
- The current main branch has a successful CI run.
- The central Agent Handoff Watchdog had a failed run because its GitHub search calls used POST semantics. This is fixed in the pre-launch PR.
- Production deployment is not considered complete until a real server returns /readyz with HTTP 200.

## Required order

| Order | Action | Owner | GitHub automation |
|---|---|---|---|
| 1 | Create repository-administration environment and require approval | Repository owner | Manual GitHub settings |
| 2 | Add REPO_ADMIN_TOKEN to that environment | Repository owner | Secret value never enters the repository |
| 3 | Run Configure Main Protection with PROTECT-MAIN before merging new work | Repository owner | .github/workflows/repository-hardening.yml |
| 4 | Review and merge the pre-launch PR after CI passes and protection is active | Repository owner | Human approval |
| 5 | Run Preflight Deployment Gates with PREFLIGHT-DEPLOYMENT and check_server=false | Repository owner | New preflight workflow |
| 6 | Lock the dedicated WorkBuddy/Buddy App to GLM-5.3-Flash and confirm it | WorkBuddy operator | Manual provider configuration |
| 7 | Create orchestrator-production environment with required approval | Repository owner | Manual GitHub settings |
| 8 | Add ORCH_SERVER_* and ORCH_ENV_B64 secrets | Repository owner | Secret values stay in GitHub |
| 9 | Run WorkBuddy Deploy Orchestrator with DEPLOY-ORCHESTRATOR | WorkBuddy deployment owner | SSH/Docker/readiness/rollback workflow |
| 10 | Add ORCHESTRATOR_URL, ORCHESTRATOR_TOKEN, and OPENAI_API_KEY to the required GitHub scope | Repository owner | Secret values stay in GitHub |
| 11 | Run Bootstrap Agent Labels once | Repository owner | GitHub Actions |
| 12 | Run Preflight Deployment Gates with check_server=true | Repository owner | Verifies live /readyz in orchestrator-production |
| 13 | Run Multi-Agent E2E Smoke with RUN-E2E | Repository owner | Synthetic data only; the E2E PR stays unmerged |
| 14 | Start the first real recruitment task only after the E2E evidence is reviewed | Codex + repository owner | Human release decision |

## Secret names

Configure values only in GitHub environment/repository secrets or the server's protected .env. Never commit them, paste them into an issue, or send them to an agent:

- REPO_ADMIN_TOKEN
- ORCH_SERVER_HOST
- ORCH_SERVER_USER
- ORCH_SERVER_PORT
- ORCH_SERVER_SSH_KEY
- ORCH_SERVER_KNOWN_HOSTS
- ORCH_SERVER_PATH
- ORCH_ENV_B64
- OPENAI_API_KEY
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN

The deployment workflow also checks the WorkBuddy credentials and the exact GLM-5.3-Flash lock in the server environment.

## Stop conditions

Stop and investigate instead of advancing the phase when:

- main protection or production approval is missing;
- the model lock is not confirmed;
- /readyz is not HTTP 200;
- the synthetic E2E chain misses a phase or handoff;
- deployment health checks fail;
- a real recruitment dataset is requested before the synthetic E2E evidence is reviewed.

Do not merge the E2E PR or bypass the protected production approval gate.
