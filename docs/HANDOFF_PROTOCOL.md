# Agent Handoff Protocol v1

## Canonical sequence

```text
Codex / product_planning
  -> OpenAI Validator / prototype_validation
  -> Account ChatGPT / implementation
  -> OpenAI Validator / qa_acceptance
  -> Codex / release_review
  -> OpenAI Validator / deployment_plan
  -> GitHub Actions / merge_and_deploy
  -> health_verification
  -> done
```

OpenAI Validator uses compatibility agent ID `workbuddy` in structured
handoffs and labels. It does not use WorkBuddy Cloud.

Account ChatGPT uses logical agent ID `chatgpt`. The implementation execution
surface is the owner's ordinary ChatGPT account using GPT-5.6 Sol High; the
retired API Sol workflow is not part of the normal chain.

An emergency ChatGPT Work GPT-6 task may substitute for the implementation
execution surface when explicitly escalated. It still publishes the same
logical `chatgpt -> workbuddy` implementation handoff so downstream gates stay
stable.

Every phase publishes `<!-- agent-handoff:v1 -->` with task ID, ownership,
phase, status, model/execution surface, artifacts, checks, blockers, source
ref/SHA and PR number.

The next phase starts only when:
- task ID matches;
- expected from/to logical agent matches;
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

Each must report `status: ready` for the chain to advance. QA also has the
repository deterministic-test gate. Production reruns repository tests
immediately before merge.

## Transport

- Codex and OpenAI Validator API phases use GitHub Actions/repository dispatch.
- Prototype success labels the current PR
  `agent:chatgpt + phase:implementation + status:todo`; it does not dispatch
  the retired API Sol implementation workflow.
- The account Chat scheduled worker automatically consumes those queued PRs.
- Account Chat publishes the implementation handoff, then adds
  `agent:workbuddy + phase:qa` and adds `status:todo` last.
- OpenAI Validator listens to that PR label event and begins QA automatically.
- The watchdog is recovery/timeout supervision, not the main transport.
