# Agent Handoff Protocol v1

## Canonical sequence

```text
Codex / product_planning
  -> WorkBuddy / prototype_validation
  -> ChatGPT / implementation
  -> WorkBuddy / qa_acceptance
  -> Codex / release_review
  -> WorkBuddy / deployment_plan
  -> GitHub Actions / merge_and_deploy
  -> health_verification
  -> done
```

No phase may skip a blocked predecessor.

## Stable task ID

The source Issue uses `GH-ISSUE-<number>`. The planning PR body carries the
same task ID and every later handoff reuses it.

## Required handoff fields

Every `agent-handoff:v1` records:
- task_id
- from_agent / to_agent
- phase / status
- model / effort
- required_inputs
- expected_outputs
- acceptance
- artifacts
- checks
- blockers
- source_ref / source_sha
- pr_number

The next phase starts only when task ID, ownership, phase, success status,
empty blockers and current PR head SHA all match.

## Phase ownership

Codex product planning outputs product/business/data/taxonomy documents.

WorkBuddy prototype validation outputs prototype, data-analysis,
classification-validation and UI/UX reports.

ChatGPT implementation outputs application code, migrations/data services and
tests.

WorkBuddy QA outputs deterministic test evidence plus classification and UI/UX
acceptance.

Codex release review outputs `CHANGELOG.md`, `docs/RELEASE_NOTES.md` and
`reports/release_gate.json`.

WorkBuddy deployment planning outputs:
- `reports/deployment_plan.md`
- `reports/deployment_gate.json`

A successful deployment plan dispatches the automatic production workflow.

## Automatic production execution

The production workflow:
1. validates the WorkBuddy deployment handoff;
2. validates release/deployment gates;
3. waits for required CI;
4. merges the PR;
5. deploys main to the persistent server;
6. checks health at 0m, 1m, 5m and 15m;
7. rolls back to the previous server SHA on failure;
8. marks the task deployed/done on success.

`AUTO_PRODUCTION_ENABLED=true` is required. `EMERGENCY_STOP=true` stops the
chain before merge/deploy.

Synthetic `[E2E]` tasks run through the deployment gate but intentionally
skip real merge/server deployment.

## Monitoring

Primary routing is real time through `repository_dispatch`.

A central watchdog runs every 10 minutes:
- queued handoff >10 minutes -> one warning;
- Codex running >55 minutes -> blocked;
- WorkBuddy running >30 minutes -> blocked;
- ChatGPT running >75 minutes -> blocked.

Failures remain blocked rather than being blindly advanced.
