# Agent Handoff Protocol v1

## Canonical sequence

```text
Codex / product_planning
  -> OpenAI Validator / prototype_validation
  -> ChatGPT / implementation
  -> OpenAI Validator / qa_acceptance
  -> Codex / release_review
  -> OpenAI Validator / deployment_plan
  -> GitHub Actions / merge_and_deploy
  -> health_verification
  -> done
```

The OpenAI Validator uses compatibility agent ID `workbuddy` in structured
handoffs and labels so existing gates remain stable. It does not use WorkBuddy
Cloud.

Every phase publishes `<!-- agent-handoff:v1 -->` with task ID, ownership,
phase, status, model, artifacts, checks, blockers, source ref/SHA and PR number.

The next phase starts only when:
- task ID matches;
- expected from/to agent matches;
- phase matches;
- status is success;
- blockers are empty;
- source SHA equals the current PR head SHA.

## Machine-readable gates

Prototype:
- `reports/prototype_gate.json`

QA:
- `reports/qa_summary.json`

Deployment:
- `reports/deployment_gate.json`

Each must report `status: ready` for the chain to advance.

QA also has a deterministic repository-test gate. Production reruns repository
tests immediately before merge.

## Transport

Primary routing is real-time through GitHub `repository_dispatch`. No agent
polls GitHub and no persistent Orchestrator is needed for normal handoffs.
