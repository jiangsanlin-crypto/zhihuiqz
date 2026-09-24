# Real Server Deployment Acceptance

This is the production acceptance standard for proving that GitHub Actions
actually controls the real server deployment path. Synthetic E2E success alone
is not sufficient because synthetic E2E intentionally skips real merge/server
deployment.

## PASS definition

Real deployment acceptance is PASS only when one workflow run proves:

1. GitHub Actions can authenticate to the configured server with strict host-key
   checking and no password prompt.
2. The target path is an existing Git repository with a usable Docker daemon and
   Docker Compose.
3. The exact current main SHA is fetched and the server HEAD is reset to that
   exact SHA.
4. docker compose up -d --build succeeds.
5. /readyz returns HTTP success, valid JSON, top-level ok=true, and every
   checks[*].ok=true.
6. Health passes at 0m, 1m, 5m and 15m after deployment.
7. The final server SHA still equals the exact accepted main SHA.
8. The workflow saves a durable evidence artifact and GitHub step summary.
9. At least one controlled rollback/recovery drill has passed before declaring
   the deployment system fully commissioned.

Any failed item blocks acceptance.

## Required secrets

The workflow never prints secret values. These repository secrets must be
usable:

- ORCH_SERVER_HOST
- ORCH_SERVER_USER
- ORCH_SERVER_SSH_KEY
- ORCH_SERVER_KNOWN_HOSTS

Optional:

- ORCH_SERVER_PORT, default 22
- ORCH_SERVER_PATH, default /opt/zhihuiqz-orchestrator

## Normal acceptance run

Run the GitHub Actions workflow:

Real Server Deployment Acceptance

Inputs:

- confirm = RUN-REAL-DEPLOY-ACCEPTANCE
- expected_sha = blank, unless explicitly pinning current main
- rollback_drill = no
- rollback_confirm = blank

The workflow refuses a requested SHA that is not current main.

## SSH acceptance

PASS requires:

- BatchMode login succeeds;
- StrictHostKeyChecking succeeds;
- no password prompt;
- target directory exists;
- target directory is a Git work tree.

## Docker Compose acceptance

PASS requires:

- docker --version succeeds;
- docker compose version succeeds;
- docker info succeeds;
- a supported Compose file exists;
- docker compose up -d --build succeeds;
- final container state can be listed.

Disk usage and Docker storage usage are recorded as evidence.

## /readyz acceptance

The fixed local readiness endpoint is:

http://127.0.0.1:8080/readyz

Every sample must satisfy:

- curl succeeds with HTTP success;
- response is valid JSON;
- top-level ok is true;
- every item under checks has ok=true.

An HTTP 200 response with {"ok": false} is a failure.

## Stability window

The same readiness gate must pass at:

- 0 minutes
- 1 minute
- 5 minutes cumulative
- 15 minutes cumulative

Any failed sample fails the deployment acceptance and invokes rollback to the
pre-deployment SHA.

## Automatic failure rollback

Before deployment the workflow records PREV_SHA.

If deployment, Docker Compose, SHA validation or readiness fails after the
deployment step begins, the workflow attempts:

- git reset --hard PREV_SHA;
- docker compose up -d --build;
- /readyz validation.

The evidence log records ROLLBACK_BEGIN and, when recovery succeeds,
ROLLBACK_RECOVERY_PASS.

A failed deployment must never be reported as accepted.

## Controlled rollback drill

The rollback drill is intentionally separate because it changes the running
server twice.

To run it explicitly:

- confirm = RUN-REAL-DEPLOY-ACCEPTANCE
- rollback_drill = yes
- rollback_confirm = RUN-ROLLBACK-DRILL

After the normal 0/1/5/15-minute acceptance passes, the drill:

1. resets the server to PREV_SHA;
2. rebuilds/restarts Docker Compose;
3. verifies /readyz on the rollback version;
4. redeploys the accepted current-main SHA;
5. verifies /readyz immediately and after one minute;
6. requires the final server SHA to equal the accepted current-main SHA.

A drill is PASS only when the old version recovers and the accepted version is
successfully restored afterward.

## Evidence required

Each run uploads an artifact named:

real-server-deployment-acceptance-<workflow-run-id>

The artifact contains:

- deployment-acceptance-report.md
- server-preflight.log
- deployment-acceptance.log

Required positive evidence markers include:

- SSH_PASS
- DOCKER_COMPOSE_PREFLIGHT_PASS
- SHA_RESOLUTION_PASS
- SERVER_SHA_MATCH_PASS
- DOCKER_COMPOSE_DEPLOY_PASS
- READYZ_0m_PASS
- READYZ_1m_PASS
- READYZ_5m_PASS
- READYZ_15m_PASS
- STABILITY_0_1_5_15_PASS
- FINAL_SERVER_SHA_PASS
- DEPLOYMENT_ACCEPTANCE_PASS

For a rollback drill, also require:

- ROLLBACK_DRILL_BEGIN
- ROLLBACK_RECOVERY_PASS
- ROLLBACK_DRILL_PASS

## Final commissioning rule

GitHub Actions may be described as having fully taken over real server
deployment only after:

- one real normal acceptance run passes against the production server; and
- at least one controlled rollback/recovery drill passes.

Synthetic E2E, static CI, and dry-run deployment gates do not replace these two
pieces of evidence.
