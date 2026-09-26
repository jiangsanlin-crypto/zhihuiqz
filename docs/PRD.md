# Synthetic E2E: Codex-to-WorkBuddy Dispatch Retry Smoke

- Task ID: `GH-ISSUE-46`
- Status: planning scope for synthetic validation
- Product change: none

## Objective

Verify the repaired Codex product-planning path after GitHub pull-request
permissions were enabled and transient GitHub API retry logic was added. The
synthetic path must run the pinned Codex model, create a planning PR, publish a
valid Codex-to-WorkBuddy handoff, and deliver the
`agent_workbuddy_prototype` repository-dispatch event to Route WorkBuddy
Tasks.

This is a control-plane smoke test. It does not add a recruitment feature or
change matching behavior.

## In scope

- Run Codex with `gpt-5.6-luna` and `max` effort, with no fallback model.
- Produce only the six product-planning artifacts in the workflow allowlist.
- Commit and push the planning artifacts from the Action-created task branch.
- Create an open specification PR automatically with the stable task marker
  `GH-ISSUE-46`.
- Publish an `agent-handoff:v1` comment with an empty blockers list and the
  exact current PR head SHA.
- Apply the WorkBuddy prototype labels and send a repository dispatch carrying
  the PR number, task ID, branch, source SHA and `prototype` phase.
- Exercise the retry-enabled PR write and dispatch path as part of the normal
  workflow run; no manual comment, label, PR or dispatch substitution is
  permitted.
- Confirm that Route WorkBuddy Tasks accepts the event and relays the
  synthetic pull-request event to the configured orchestrator.

## Out of scope

- Real candidate, employer, payment, billing or personally identifiable data.
- Recruitment application code, database migrations, ranking changes or
  taxonomy changes.
- Manual PR creation, handoff substitution, branch-protection bypass or
  direct server execution.
- PR merge, production deployment, production health checks or rollback.

## Acceptance evidence

The smoke is accepted only when the remote workflow evidence shows all of the
following:

1. The source issue resolves to `GH-ISSUE-46`, and the Codex Action succeeds
   with `gpt-5.6-luna` / `max` and no fallback.
2. The product-only file allowlist passes and the planning commit is pushed.
3. GitHub Actions creates an open specification PR whose body contains
   `<!-- agent-task-id:GH-ISSUE-46 -->`.
4. A PR comment contains `<!-- agent-handoff:v1 -->` and valid JSON with
   `task_id: GH-ISSUE-46`, `from_agent: codex`, `to_agent: workbuddy`,
   `phase: product_planning`, `status: success`, `blockers: []`,
   `source_sha` equal to the current PR head SHA, and `pr_number` equal to
   the created PR.
5. The PR has `agent:workbuddy`, `phase:prototype` and `status:todo`, and the
   `agent_workbuddy_prototype` dispatch is accepted by Route WorkBuddy Tasks
   with matching task and source-SHA data.
6. The route workflow reaches its synthetic pull-request relay step. Any
   transient PR-write or dispatch failure is retried by the checked-in
   workflow before the smoke is marked failed.
7. No real data, merge, deployment or business transaction occurs.

The local planning artifact does not assert that the remote Action, PR or
route succeeded; those claims require the corresponding GitHub Actions and
orchestrator run evidence.

## Product safety invariant

GitHub permissions, retry attempts, workflow status, PR labels, handoff
metadata, branch names and source SHAs are operational metadata only. They
must never be treated as job requirements, candidate attributes,
classification labels or relevance signals. Paid employer features must
never directly increase a relevance score.
