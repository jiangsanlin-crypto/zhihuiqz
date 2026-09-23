# Three-Agent Activation Runbook

## 1. Review PR #1

Require:
- CI success;
- mergeable PR;
- no committed secrets;
- model-policy check success;
- human review of role/permission boundaries.

Do not enable auto-merge.

## 2. Confirm WorkBuddy model lock

In the dedicated WorkBuddy/Buddy App:
1. expose only GLM-5.3-Flash;
2. set it as default;
3. verify no Auto/other model can be selected for this integration;
4. set `WORKBUDDY_MODEL_LOCK_CONFIRMED=true` only after verification.

## 3. Prepare persistent Linux server

Required:
- Git
- Docker Engine
- Docker Compose plugin
- outbound HTTPS access
- SSH access from GitHub Actions

Create the GitHub environment:
`orchestrator-production`

Require human approval.

Configure the ORCH_SERVER_* secrets and ORCH_ENV_B64.

## 4. Human merge

Merge PR #1 to main only after the above review.

Immediately protect main.

## 5. Deploy Orchestrator

Run:

`Actions -> WorkBuddy Deploy Orchestrator`

Input:

`DEPLOY-ORCHESTRATOR`

The workflow verifies `/readyz` and rolls back on failure.

## 6. Configure normal runtime secrets

GitHub Actions:
- OPENAI_API_KEY
- AGENT_GITHUB_TOKEN
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN

Server `.env`:
- Orchestrator GitHub token/repository
- WorkBuddy OAuth
- WorkBuddy model lock
- Orchestrator/WorkBuddy bearer tokens

## 7. Bootstrap labels

Run `Bootstrap Agent Labels` once.

## 7.5 Configure automation identity

Create `AGENT_GITHUB_TOKEN` as a fine-grained token scoped only to this repository with Contents, Issues and Pull requests read/write. It must not bypass protected `main`. This token is used for agent branch pushes, PR comments/labels and `repository_dispatch`, so cross-workflow handoffs are not suppressed by GitHub's `GITHUB_TOKEN` recursion protection.

## 8. Run synthetic E2E

Run `Multi-Agent E2E Smoke` with `RUN-E2E`.

Expected chain:
1. Codex product_planning
2. WorkBuddy prototype_validation
3. ChatGPT implementation
4. WorkBuddy qa_acceptance
5. Codex release_review
6. human review state

The E2E PR must stay unmerged.

## 9. Release workflow

After a real PR passes Codex release review:
- human reviews and merges main;
- optionally run `Codex Create Draft Release`;
- human approves production;
- WorkBuddy owns the approved deployment run and health checks.

## 10. Monitoring

Normal operation is real time.

Do not create three independent polling loops.

The central watchdog runs every 10 minutes:
- queued handoff >10 minutes -> one warning;
- Codex running >55 minutes -> blocked;
- WorkBuddy running >30 minutes -> blocked;
- ChatGPT running >75 minutes -> blocked.

Deployment health is checked more aggressively during the first 15 minutes.

## 11. Failure rule

Never skip to the next agent when a phase is blocked.

Fix the blocker and retry the same phase using the relevant manual `workflow_dispatch` entry point. Labels alone are state markers and are not relied upon to chain workflows.
