# Shadow Test Result — 2026-09-23

Classification: **PASS-B**

The account-backed ChatGPT GPT-5.6 Sol path successfully completed the engineering round-trip, but unattended GitHub-event -> ChatGPT Work execution was not proven in this run.

## Test artifacts

- Source issue: #53 — `[SHADOW] ChatGPT account Sol implementation round-trip`
- Draft implementation PR: #54 — `test: ChatGPT account Sol shadow implementation`
- Test branch: `shadow/chatgpt-account-sol-53`
- Resulting head SHA: `3612577224d932df41cf4be132a64b4556e72d30`
- CI run: `35879509086`

## What was tested

The interactive ChatGPT account session running GPT-5.6 Sol:

1. consumed the GitHub task and exact acceptance criteria;
2. created a dedicated non-production branch;
3. created only:
   - `tests/chatgpt_account_worker_marker.txt`
   - `tests/test_chatgpt_account_worker_marker.py`;
4. opened a draft PR;
5. did not add the normal `agent:chatgpt` / `phase:implementation` labels;
6. did not dispatch the API-backed `ChatGPT Implementation` workflow;
7. relied on ordinary repository CI for deterministic verification.

## Deterministic evidence

CI run `35879509086` completed successfully.

Observed successful CI steps included:

- dependency installation;
- `python -m compileall -q orchestrator scripts tests`;
- `PYTHONPATH=. pytest -q`;
- model-policy check;
- dispatch-policy check;
- full-auto-policy check;
- workflow YAML validation;
- Docker Compose validation.

The commit-associated workflow set for the shadow branch contained the ordinary `CI` run. No `ChatGPT Implementation` run was created for the shadow branch.

Recent API-backed `ChatGPT Implementation` runs visible at the time of the test were older, unrelated repository-dispatch runs and predated the shadow PR.

## What this proves

This run proves that the ChatGPT account GPT-5.6 Sol path can:

- understand a GitHub engineering task;
- produce exact repository changes;
- write those changes to a GitHub branch through the connected GitHub tool;
- open a reviewable PR;
- obtain deterministic CI evidence;
- operate without invoking the repository's API-backed AI implementation workflow for this task.

## What this does not prove

This run did not prove:

- unattended GitHub webhook/repository event triggering a ChatGPT Work task;
- a persistent ChatGPT Work sandbox running without an interactive start;
- automated `agent-handoff:v1` publication from a ChatGPT Work task;
- long-running/retry behavior under ChatGPT Work;
- billing/accounting attribution beyond the fact that the repository API implementation workflow was not invoked.

Those are required for PASS-A.

## Next gate

The next non-production experiment should start the same kind of task from an actual ChatGPT Work automation/event trigger, then require:

1. exact PR/task/head-SHA intake;
2. branch-only implementation;
3. CI success;
4. valid `agent-handoff:v1`;
5. evidence that no `OPENAI_API_KEY` AI workflow was used;
6. retry behavior after one forced interruption.

Do not replace the current API worker until that unattended path reaches PASS-A repeatedly.
