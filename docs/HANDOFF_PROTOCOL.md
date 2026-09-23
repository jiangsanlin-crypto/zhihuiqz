# Agent Handoff Protocol v1

The same stable task ID follows the work from the source Issue through every
phase.

## Canonical sequence

```text
Codex / product_planning
  -> WorkBuddy / prototype_validation
  -> ChatGPT / implementation
  -> WorkBuddy / qa_acceptance
  -> Codex / release_review
  -> Human / merge + production approval
  -> WorkBuddy / deployment
```

No AI work body may skip a blocked phase.

## Stable task ID

The source Issue uses:

`GH-ISSUE-<number>`

The planning PR body contains:

`<!-- agent-task-id:GH-ISSUE-<number> -->`

Every later handoff reuses the same ID.

## Handoff record

Every phase publishes a PR/Issue comment starting with:

`<!-- agent-handoff:v1 -->`

The JSON payload records:
- task_id;
- from_agent / to_agent;
- phase / status;
- exact model and effort;
- required_inputs;
- expected_outputs;
- acceptance criteria;
- artifacts;
- checks;
- blockers;
- source_ref / source_sha;
- pr_number.

The next agent must read the latest successful handoff and all referenced
artifacts before working.

## Phase contracts

### Codex product planning

Inputs:
- source Issue;
- public repository;
- current product documents.

Outputs:
- docs/PRD.md
- docs/RECRUITMENT_RULES.md
- docs/DATA_COLLECTION_PLAN.md
- docs/CLASSIFICATION_DICTIONARY.md
- TASKS.md
- CHANGELOG.md

Next owner: WorkBuddy.

### WorkBuddy prototype validation

Inputs:
- Codex planning documents;
- planning PR;
- prior handoff.

Outputs:
- reports/prototype_review.md
- reports/data_analysis.md
- reports/classification_validation.md
- reports/uiux_prototype.md

Next owner: ChatGPT only when successful.

### ChatGPT implementation

Inputs:
- Codex planning documents;
- WorkBuddy prototype reports;
- prior handoffs.

Outputs:
- application code;
- tests;
- migrations/data services as needed;
- implementation handoff containing changed files and commit SHA.

Next owner: WorkBuddy.

### WorkBuddy QA acceptance

Inputs:
- ChatGPT implementation;
- product specification;
- prototype reports;
- deterministic test evidence;
- prior handoffs.

Outputs:
- reports/test_report.md
- reports/uiux_acceptance.md
- reports/classification_validation.md
- reports/qa_summary.json

Next owner: Codex only when successful.

### Codex release review

Inputs:
- product documents;
- implementation handoff;
- WorkBuddy QA reports;
- PR diff / CI status.

Outputs:
- CHANGELOG.md
- docs/RELEASE_NOTES.md
- reports/release_gate.json

Next owner: Human when ready; otherwise blocked.

### Human approval

Only the human owner may:
- merge main;
- approve production deployment;
- authorize real candidate data or payment connections.

### WorkBuddy deployment

Inputs:
- approved main SHA;
- release notes;
- deployment target;
- rollback SHA;
- health endpoint.

Execution:
- GitHub Actions performs SSH/Docker commands;
- WorkBuddy owns deployment review, health verification and rollback decision.

## Monitoring

Primary handoff is event-driven and real-time through GitHub labels/actions and
the Orchestrator webhook.

Agents do **not** individually poll GitHub on timers.

A central watchdog runs every 10 minutes only as a recovery layer.

Queue policy:
- any `status:todo + agent:*` handoff older than 10 minutes -> one warning for that agent/phase;
- the watchdog does not skip the phase or start another agent.

Running-time policy:
- Codex > 55 minutes -> `status:blocked`;
- WorkBuddy > 30 minutes -> `status:blocked`;
- ChatGPT > 75 minutes -> `status:blocked`.

The timeout values reflect the expected workload of each work body. This avoids
three independent polling loops, duplicate model calls and overlapping writes
while still detecting lost events and hung jobs.
