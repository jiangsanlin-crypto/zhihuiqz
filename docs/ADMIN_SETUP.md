# Repository Administration Setup

These settings cannot be performed by the normal GitHub App connection because
repository administration and secret management are intentionally excluded.

## Main protection

Preferred automated path:

1. Create a fine-grained GitHub token owned by the repository owner.
2. Scope it only to `jiangsanlin-crypto/zhihuiqz`.
3. Grant repository Administration: Read and write.
4. Store it as GitHub secret `REPO_ADMIN_TOKEN`.
5. Create environment `repository-administration`.
6. Require human approval for that environment.
7. Run `Configure Main Protection`.
8. Enter `PROTECT-MAIN`.

The workflow enforces:
- PR required for main;
- one approving review;
- CODEOWNERS review;
- stale review dismissal;
- last-push approval;
- CI job `test` required and up to date;
- conversation resolution;
- force-push disabled;
- deletion disabled;
- admin enforcement.

Do not put the token in Issues, commits or chat messages.

## Orchestrator deployment

See `docs/DEPLOYMENT_HANDOFF.md`.

Secrets are configured through GitHub Settings, never through repository files.

## WorkBuddy model lock

The dedicated WorkBuddy app must expose only GLM-5.3-Flash before
`WORKBUDDY_MODEL_LOCK_CONFIRMED=true` is set on the server.

## Final activation order

1. Configure main protection.
2. Configure WorkBuddy model lock.
3. Configure runtime/deployment secrets.
4. Deploy Orchestrator.
5. Confirm `/readyz` is HTTP 200.
6. Run the synthetic E2E workflow.
7. Begin real product tasks.
