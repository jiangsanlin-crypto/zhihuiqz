# ChatGPT Account/Work Shadow Test Protocol

Goal: determine whether the primary implementation employee can be moved from API-backed `gpt-5.6-sol` execution to ChatGPT account/Work execution while preserving the GitHub control plane.

This is a **non-production** protocol. It must not merge to `main` or deploy production.

## Baseline

Current implementation worker:

```text
repository_dispatch
  -> .github/workflows/chatgpt-dev.yml
  -> OPENAI_API_KEY
  -> gpt-5.6-sol / high
  -> branch edits + tests + handoff
```

Shadow candidate:

```text
GitHub task/PR event
  -> ChatGPT account / Work task
  -> GPT-5.6 Sol
  -> isolated working context
  -> branch-only code result
  -> GitHub mechanical writeback
  -> existing CI + handoff validation
```

## Required proof points

A shadow run passes only if all are evidenced:

1. **Trigger/context** — the worker receives the exact PR number, task ID, branch, head SHA, acceptance criteria, and prior handoffs.
2. **No API reasoning dependency** — the AI reasoning step does not require repository `OPENAI_API_KEY`.
3. **Implementation** — the worker makes the requested non-production code/test change.
4. **Verification** — deterministic tests or the repository CI pass on the produced branch.
5. **Writeback** — only the test branch is modified; protected orchestration paths remain untouched.
6. **Handoff** — output can be converted to a valid `agent-handoff:v1` whose `source_sha` equals the resulting PR head.
7. **Recovery** — a failed or interrupted run can be retried without concurrent writers.
8. **Accounting** — the test records whether the AI step was executed in ChatGPT account/Work rather than through the API workflow.

## Test task

Use a dedicated branch/PR with a tiny deterministic requirement, for example:

```text
Create tests/chatgpt_account_worker_marker.txt
with exact content:
CHATGPT_ACCOUNT_WORKER_OK
```

Optionally add a deterministic repository test that asserts the marker's exact content.

The existing API implementation workflow must not be dispatched for the same shadow task.

## Acceptance

Classify the result:

- **PASS-A** — account-backed Sol solved the task, writeback and CI succeeded, and no API AI call was used.
- **PASS-B** — account-backed Sol solved the task and CI succeeded, but GitHub event -> ChatGPT account execution still required a manual start.
- **BLOCKED** — account-backed model could not receive context, execute reliably, write back safely, or prove non-API execution.

Only PASS-A justifies replacing the existing automatic implementation worker. PASS-B justifies further trigger/automation work, not production migration.

## Important distinction

A successful interactive ChatGPT session proves the model can perform the engineering task, but it does **not** by itself prove unattended GitHub-event triggering. These are separate test dimensions and must be reported separately.
