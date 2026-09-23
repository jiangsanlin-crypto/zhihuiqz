# Three-Agent Activation Runbook

## 0. Current state

PR #1 has already been merged. Review the current pre-launch PR and its CI result before changing production settings. The repository is not production-ready merely because the code is merged: branch protection, WorkBuddy's model lock, server secrets, readiness, and synthetic E2E still require verification.

## 1. Establish the administrative gate

Create the repository-administration GitHub environment and require human approval. Add REPO_ADMIN_TOKEN there. Do not put the token in the repository or share it with any agent.

Run Configure Main Protection with:

PROTECT-MAIN

Review and merge PR #14 only after its CI passes and main protection is active. Do not enable auto-merge.

After the merge, run Preflight Deployment Gates with:

PREFLIGHT-DEPLOYMENT

and check_server=false.

The preflight must verify required status checks, one approving review, code-owner review, conversation resolution, no force-push/deletion, the production approval environment, and the agent labels.

## 2. Confirm WorkBuddy's model lock

In the dedicated WorkBuddy/Buddy App:

1. expose only GLM-5.3-Flash;
2. set it as the default;
3. verify that Auto and other models cannot be selected for this integration;
4. set WORKBUDDY_MODEL_LOCK_CONFIRMED=true only after verification.

## 3. Prepare the persistent Linux server

The server needs Git, Docker Engine, the Docker Compose plugin, outbound HTTPS, and SSH access from GitHub Actions.

Create the GitHub environment orchestrator-production and require human approval. Configure:

- ORCH_SERVER_HOST
- ORCH_SERVER_USER
- ORCH_SERVER_PORT
- ORCH_SERVER_SSH_KEY
- ORCH_SERVER_KNOWN_HOSTS
- ORCH_SERVER_PATH
- ORCH_ENV_B64

The protected server .env must contain the orchestrator and WorkBuddy runtime credentials, repository identity, bearer tokens, and the confirmed WorkBuddy model lock.

## 4. Deploy the Orchestrator

Run Actions -> WorkBuddy Deploy Orchestrator with:

DEPLOY-ORCHESTRATOR

The workflow performs SSH, protected .env transfer, public main checkout, Docker Compose build/up, /readyz verification, and automatic rollback to the previous SHA on a failed deployment.

Do not report deployment success until /readyz is HTTP 200.

## 5. Configure runtime and run checks

Configure these GitHub Actions secrets:

- OPENAI_API_KEY
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN

Run Bootstrap Agent Labels once. Then run Preflight Deployment Gates with PREFLIGHT-DEPLOYMENT and check_server=true.

Finally run Multi-Agent E2E Smoke with RUN-E2E. It must use synthetic data and must leave its PR unmerged.

## 6. Release and monitoring rules

After a real task passes the Codex release review:

- a human reviews and merges the application PR;
- production deployment remains behind the protected environment approval;
- WorkBuddy owns deployment health checks and controlled rollback;
- the central watchdog runs every 15 minutes as a safety net;
- a blocked phase is repaired and rerun; it is never silently skipped.

The temporary sandbox is not the long-lived production service.
