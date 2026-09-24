# Agent Handoff Protocol v1

## Canonical sequence

```text
Codex / product_planning
  -> OpenAI Validator / prototype_validation
  -> Account ChatGPT / implementation
  -> Work GPT-6 / code_review
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

Work GPT-6 has two distinct duties:
- mandatory independent code review after every normal ChatGPT implementation;
- emergency/high-difficulty implementation or recovery when explicitly escalated.

Normal implementation publishes `chatgpt -> workreview` with phase
`implementation`. Work review publishes `workreview -> workbuddy` with phase
`code_review` before Luna QA may start.

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
  `agent:workreview + phase:code-review` and adds `status:todo` last.
- The Work review worker audits the diff and may repair clear defects on the
  same PR head branch. After exact-final-SHA CI succeeds it publishes the
  code-review handoff, adds `agent:workbuddy + phase:qa`, and adds
  `status:todo` last.
- OpenAI Validator listens to that final QA label event and begins QA automatically.
- The handoff reconciler treats a valid owner-authored account handoff comment as
  the source of truth for account-owned state transitions. It validates task ID,
  exact current head SHA, success status and empty blockers, then converges the
  PR labels to the canonical next owner/phase. It preserves an already-running
  target phase instead of re-queueing it.
- For a queued transition, the reconciler always adds owner + phase before
  adding `status:todo` last, so label-triggered QA cannot start on an incomplete
  state.
- Reconciliation runs immediately on qualifying handoff comments and also every
  five minutes as an eventual-recovery sweep. This makes partial label mutation
  recoverable without a human relay.
- The watchdog remains timeout supervision, not the main transport.
