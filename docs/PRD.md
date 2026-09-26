# Synthetic E2E: PR Permission and Handoff Smoke

- Task ID: `GH-ISSUE-43`
- Status: planning scope for synthetic validation
- Product change: none

## Objective

Verify that the Codex product-planning GitHub Action can complete its pinned
runtime, commit the planning artifacts, create a specification pull request,
publish a valid `agent-handoff:v1`, and trigger the WorkBuddy prototype route
after GitHub Actions pull-request permissions were enabled.

This is a control-plane smoke test. It does not add a recruitment feature or
change matching behavior.

## In scope

- Run Codex with the repository policy pin `gpt-5.6-luna` and `max` effort,
  with no fallback model.
- Produce only the six product-planning artifacts in the planning allowlist.
- Commit and push those artifacts from the Action-created task branch.
- Create a PR automatically with the stable task marker
  `GH-ISSUE-43`.
- Publish a successful Codex-to-WorkBuddy handoff containing the required
  fields, an empty blockers list, and the exact PR head SHA.
- Add the WorkBuddy prototype labels and dispatch the
  `agent_workbuddy_prototype` event with the task ID, branch, source SHA and
  `prototype` phase.
- Confirm the route workflow accepts the event and relays a synthetic
  pull-request event to the configured orchestrator.

## Out of scope

- Real candidate, employer, payment, billing or personally identifiable data.
- Recruitment application code, database migrations, ranking changes or
  taxonomy changes.
- Manual PR creation, manual handoff substitution or bypassing branch
  protection and workflow gates.
- PR merge, production deployment, health checks against production or
  rollback. This synthetic E2E intentionally stops before those actions.

## Acceptance evidence

The smoke is accepted only when the remote workflow evidence shows all of the
following:

1. The source issue resolves to `GH-ISSUE-43` and the Codex Action succeeds.
2. The Action uses `gpt-5.6-luna` with `max` effort and no fallback.
3. The product-only allowlist passes and the planning commit is pushed.
4. GitHub Actions creates an open specification PR whose body contains
   `<!-- agent-task-id:GH-ISSUE-43 -->`.
5. The PR has the WorkBuddy prototype labels: `agent:workbuddy`,
   `phase:prototype` and `status:todo`.
6. A PR comment contains `<!-- agent-handoff:v1 -->` and valid JSON with
   `task_id: GH-ISSUE-43`, `from_agent: codex`, `to_agent: workbuddy`,
   `phase: product_planning`, `status: success`, `blockers: []`,
   `source_sha` equal to the current PR head SHA, and `pr_number` equal to
   the created PR.
7. The `agent_workbuddy_prototype` repository dispatch is accepted by the
   route workflow, and the synthetic pull-request event reaches the WorkBuddy
   orchestrator route.
8. No real data, merge, deployment or business transaction occurs.

The local planning artifact does not by itself assert that the remote Action,
PR or route succeeded; those claims require the corresponding GitHub and
orchestrator run evidence.

## Product safety invariant

GitHub permissions, workflow status, PR labels, handoff status, branch names
and source SHAs are operational metadata only. They must never be treated as
job requirements, candidate attributes, classification labels or relevance
signals. Paid employer features must never directly increase a relevance
score.
