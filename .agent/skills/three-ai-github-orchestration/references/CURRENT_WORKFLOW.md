# Current Workflow Snapshot

Snapshot base: `main@743aacba168a4f40c1b53d5a362a68316ba92989` on 2026-09-23.

This file records the effective orchestration inputs used to author the companion skill. It is a snapshot, not a replacement for reading the live workflows.

## Effective workflow files

- `.github/workflows/codex-task.yml`
  - product planning and release review
  - `openai/codex-action@v1`
  - `gpt-5.6-luna`
  - effort `max`
- `.github/workflows/chatgpt-dev.yml`
  - primary implementation
  - `openai/codex-action@v1`
  - `gpt-5.6-sol`
  - effort `high`
  - implementation job timeout: 110 minutes
- `.github/workflows/openai-validator.yml`
  - prototype validation, QA, deployment readiness
  - `openai/codex-action@v1`
  - `gpt-5.6-luna`
  - effort `high`
  - structured handoffs still use compatibility agent ID `workbuddy`
- `.github/workflows/agent-watchdog.yml`
  - queued warning: 10 minutes
  - Codex running timeout: 55 minutes
  - validator prototype/QA timeout: 30 minutes
  - validator deployment timeout: 45 minutes
  - ChatGPT running timeout: 120 minutes
- `.github/workflows/auto-production-deploy.yml`
  - production executor and health/rollback path
  - must remain behind explicit human production approval in operational use
- `.github/workflows/e2e-smoke.yml`
  - synthetic end-to-end validation
  - synthetic runs must never perform a real production deployment

## Handoff/gate sources

- `.agent/handoff.schema.json`
- `scripts/validate_handoff.py`
- `docs/HANDOFF_PROTOCOL.md`

Canonical logical chain:

```text
Codex product_planning
  -> OpenAI Validator prototype_validation
  -> ChatGPT implementation
  -> OpenAI Validator qa_acceptance
  -> Codex release_review
  -> OpenAI Validator deployment_plan
  -> deterministic production checks
  -> approved merge/deploy
  -> health verification
```

## Documentation drift found during snapshot

Some older prose is not aligned with the effective current workflow.

Examples observed on this snapshot:

- `docs/ARCHITECTURE.md` still describes WorkBuddy Cloud/persistent Orchestrator routing and older `gpt-6-*` names.
- `docs/MODEL_POLICY.md` has current OpenAI model pins at the top but retains an older WorkBuddy Cloud enforcement section.
- `docs/ROLE_MATRIX.md` and `docs/HANDOFF_PROTOCOL.md` reflect the newer OpenAI Validation Agent architecture.

Therefore the skill intentionally treats live GitHub workflows and the handoff validator as higher priority than stale prose.

Do not silently rewrite those historical docs while handling an unrelated product task. Fix documentation drift in a dedicated maintenance PR.
