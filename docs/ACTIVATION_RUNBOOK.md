# Multi-Agent Activation Runbook

This runbook takes the system from a passing code review to the first real end-to-end agent chain.

## 1. Before merge

PR #1 must have:
- CI passing;
- mergeable state;
- human review of the orchestrator permission model;
- no production credentials committed.

Do not enable automatic merge.

## 2. Merge and protect main

After human approval, merge PR #1 manually.

Immediately protect main:
- require pull requests;
- require CI/status checks;
- block force pushes;
- do not allow agent bypass.

## 3. Persistent server

On the server:

```bash
git clone https://github.com/jiangsanlin-crypto/zhihuiqz.git
cd zhihuiqz
cp .env.example .env
```

Fill `.env` locally. Do not commit it.

Generate independent random bearer tokens for:
- ORCHESTRATOR_TOKEN
- WORKBUDDY_TOKEN
- SANDBOX_TOKEN

Set the WorkBuddy API/OAuth credentials and the Orchestrator GitHub write credential.

## 4. Static preflight

```bash
python scripts/preflight.py --env-file .env
```

Every item must report PASS.

## 5. Start services

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz
```

`/readyz` must return HTTP 200 and `"ok": true`.

If it returns 503, do not start an agent task. Fix the failed check first.

## 6. GitHub Actions secrets

Configure:
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN
- OPENAI_API_KEY

ORCHESTRATOR_URL must be the HTTPS public address of the persistent Orchestrator.

## 7. Bootstrap labels

Run the `Bootstrap Agent Labels` workflow once.

## 8. Manual synthetic E2E smoke

Run:

`Actions -> Multi-Agent E2E Smoke -> Run workflow`

Enter:

`RUN-E2E`

The workflow deliberately creates a synthetic Issue and PR and validates:

1. WorkBuddy specification handoff;
2. Sandbox specification QA;
3. Codex implementation;
4. Sandbox final QA;
5. WorkBuddy final product review;
6. final state is human review;
7. Codex created the harmless smoke marker.

The smoke PR is intentionally left open and unmerged for inspection.

## 9. Expected final state

The synthetic PR should contain handoff comments for:
- specification
- spec_qa
- implementation
- final_qa
- product_review

It should end at `status:review` with no active `agent:*` label.

## 10. Failure handling

If any stage reaches `status:blocked`:
- do not manually jump to the next agent;
- inspect the latest `agent-handoff:v1` blocker;
- fix the reported problem;
- reapply the appropriate agent label to retry that same phase.

If the Orchestrator is unavailable:
- GitHub remains the durable task record;
- no agent should be advanced manually until the Orchestrator is healthy.

## 11. Rollback

No workflow automatically deploys production.

If the orchestration release itself must be rolled back:
1. stop creating new agent Issues;
2. stop the Orchestrator containers;
3. revert the orchestration commit through a normal PR;
4. preserve existing Issue/PR handoff history;
5. restart only after CI and preflight pass.

Never solve an orchestration incident by bypassing main protection or handing broad GitHub credentials to WorkBuddy/Sandbox.
