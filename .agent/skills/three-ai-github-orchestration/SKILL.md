---
name: three-ai-github-orchestration
description: Operate, debug, preserve, or migrate this repository's three-AI GitHub workflow: Codex product/release, ChatGPT implementation, and the OpenAI Validation Agent, including agent-handoff:v1 gates, repository_dispatch routing, watchdog recovery, CI, deployment readiness, and production safety.
---

# Three-AI GitHub Orchestration

Use this skill whenever the task is about the repository's AI employees, handoffs, routing, stuck jobs, model policy, workflow migration, validator behavior, GitHub labels, watchdogs, release gates, or deployment readiness.

## Source-of-truth order

Do not infer the live architecture from old prose alone. Resolve conflicts in this order:

1. current files under `.github/workflows/`;
2. `.agent/handoff.schema.json` and `scripts/validate_handoff.py`;
3. current role prompts under `agents/`;
4. `docs/HANDOFF_PROTOCOL.md`, `docs/ROLE_MATRIX.md`, and current gate documents;
5. older architecture/deployment prose only as historical context.

Before changing orchestration, re-read the relevant live workflow files from the target branch.

## Effective three work bodies

The logical employees are:

- **Codex** — product planning and release review. Current API workflow pin: `gpt-5.6-luna`, effort `max`.
- **ChatGPT** — primary implementation engineer. Current API workflow pin: `gpt-5.6-sol`, effort `high`.
- **OpenAI Validation Agent** — prototype review, data/classification validation, deterministic QA, multilingual UI/UX acceptance, and deployment-readiness review. Current API workflow pin: `gpt-5.6-luna`, effort `high`.

The validation agent keeps the compatibility ID `workbuddy` in labels and `agent-handoff:v1`. Compatibility naming does **not** mean WorkBuddy Cloud is active.

## Canonical state machine

Normal sequence:

```text
GitHub Issue
  -> Codex / product_planning
  -> OpenAI Validation Agent / prototype_validation
  -> ChatGPT / implementation
  -> OpenAI Validation Agent / qa_acceptance
  -> Codex / release_review
  -> OpenAI Validation Agent / deployment_plan
  -> deterministic repository tests
  -> human-approved merge/deployment path
  -> health verification
  -> done
```

Primary transport is event-driven with GitHub `repository_dispatch`. Never create independent polling loops for the three work bodies.

## Stable task identity

For an Issue-backed task, use:

```text
GH-ISSUE-<issue_number>
```

The planning PR must preserve:

```html
<!-- agent-task-id:GH-ISSUE-<issue_number> -->
```

Every later phase must reuse the exact same task ID.

## Handoff contract

Every AI phase emits a PR/Issue comment beginning exactly with:

```html
<!-- agent-handoff:v1 -->
```

The JSON payload must conform to `.agent/handoff.schema.json` and include at least:

- version
- task_id
- from_agent
- to_agent
- phase
- status
- summary
- model
- effort
- required_inputs
- expected_outputs
- acceptance
- artifacts
- checks
- blockers
- source_ref
- source_sha
- pr_number

A downstream phase may start only when all of these are true:

- task ID matches;
- expected from/to agent matches;
- phase matches;
- status is `success`;
- blockers is empty;
- source SHA equals the current PR head SHA.

Never repair a SHA mismatch by weakening validation. Re-emit the handoff against the actual full PR head SHA.

## Machine-readable gates

Expected gate files:

- prototype: `reports/prototype_gate.json`
- QA: `reports/qa_summary.json`
- release: `reports/release_gate.json`
- deployment: `reports/deployment_gate.json`

The applicable gate must be structurally valid and report the expected ready/success state before advancing.

Deterministic repository tests are authoritative. If tests fail, AI prose cannot override the failure.

## Labels and phase ownership

Typical ownership labels:

- `agent:codex`
- `agent:chatgpt`
- `agent:workbuddy` (OpenAI Validation Agent compatibility ID)

Phase labels:

- `phase:product-plan`
- `phase:prototype`
- `phase:implementation`
- `phase:qa`
- `phase:release`
- `phase:deploy`

Status labels:

- `status:todo`
- `status:running`
- `status:blocked`
- `status:review`
- `status:done`
- `status:deployed`

Do not advance a blocked task by relabeling it to a later phase. Fix the blocker and retry the same phase.

## Watchdog policy

The watchdog is recovery-only; it is not the task transport.

At the current snapshot:

- queued handoff warning: after 10 minutes;
- Codex running timeout: 55 minutes;
- validator prototype/QA timeout: 30 minutes;
- validator deployment timeout: 45 minutes;
- ChatGPT implementation watchdog: 120 minutes;
- ChatGPT implementation GitHub job timeout: 110 minutes.

When tuning timeouts, the workflow job timeout must expire before the watchdog marks the same healthy run stale.

## Permission boundaries

- Codex planning may update only the planning allowlist defined by its workflow.
- Codex release review may update only release artifacts allowed by its workflow.
- ChatGPT may implement on the active PR branch but must not modify protected orchestration/product-policy paths unless the maintenance task explicitly targets orchestration and is handled through a separate reviewed maintenance PR.
- The validation agent writes only the phase-specific reports/gates allowed by its workflow.
- AI workers do not bypass branch protection.
- Synthetic E2E tasks must never merge or deploy production.

## Production safety

Never perform a real production deployment merely because an AI gate says ready.

Before production merge/deploy:

1. confirm all required CI/checks are green;
2. confirm the deployment gate references the current PR head;
3. confirm rollback and health checks are defined;
4. obtain explicit human approval for that production action;
5. only then allow the production executor to proceed.

## Failure recovery

When a phase fails:

1. inspect the exact GitHub Actions job/step and latest handoff;
2. distinguish routing failure, model failure, invalid handoff, test failure, protected-path violation, or timeout;
3. fix the narrow cause;
4. restore that same phase to `status:todo`;
5. re-dispatch only that phase;
6. verify no overlapping stale run is still active.

Do not start a second worker for the same phase while an earlier run may still write to the same PR branch.

## Migration to ChatGPT account/Work execution

The current API-based workflow is the control baseline. Any migration of the ChatGPT implementation employee to ChatGPT account/Work execution must be **shadow-tested first**.

The migration is acceptable only if the account-backed worker can demonstrate, without relying on `OPENAI_API_KEY` for the AI reasoning step:

- exact GitHub task/PR context intake;
- correct use of the stable task ID and current head SHA;
- repository-aware code generation;
- deterministic test execution or externally verifiable CI;
- branch-only writeback;
- valid `agent-handoff:v1` output;
- no protected-path or production access;
- reliable retry/recovery behavior.

Keep the API worker available as a fallback until the shadow path passes repeated non-production tests. Do not run both workers concurrently on the same implementation phase.
