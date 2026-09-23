# WorkBuddy Deployment Handoff

## Owner

Deployment owner: **WorkBuddy**

Command executor: **GitHub Actions**

Final production approver: **Human owner**

WorkBuddy does not SSH to production ad hoc and does not overwrite server files
directly. The approved workflow is the only deployment path.

## Initial Orchestrator bootstrap

The first persistent Orchestrator deployment uses:

`Actions -> WorkBuddy Deploy Orchestrator`

Human input:

`DEPLOY-ORCHESTRATOR`

GitHub environment:

`orchestrator-production`

The environment should require human approval.

Required repository/environment secrets:
- ORCH_SERVER_HOST
- ORCH_SERVER_USER
- ORCH_SERVER_PORT
- ORCH_SERVER_SSH_KEY
- ORCH_SERVER_KNOWN_HOSTS
- ORCH_SERVER_PATH
- ORCH_ENV_B64

`ORCH_ENV_B64` is the base64-encoded server `.env` file. It must never be
committed.

## Handoff into deployment

Codex release review hands to the human owner.

The human owner:
1. reviews the PR and release gate;
2. merges main;
3. approves production deployment.

Only then does WorkBuddy own the deployment phase.

WorkBuddy deployment inputs:
- approved main SHA;
- release notes;
- WorkBuddy QA reports;
- rollback SHA;
- server health endpoint;
- deployment workflow run ID.

WorkBuddy deployment outputs:
- deployed SHA;
- Docker service status;
- `/readyz` result;
- post-deploy health observations;
- rollback decision/result;
- final deployment summary.

## Health sequence

The deployment workflow checks readiness immediately and with delayed retries.
For application releases, WorkBuddy should additionally check at approximately:
- 0 minutes;
- 1 minute;
- 5 minutes;
- 15 minutes after deployment.

A failed mandatory health check blocks completion and triggers rollback where
the workflow has a known previous SHA.
