# TASKS

## JOB-001 — Multilingual recruitment matching

Owner sequence:

```text
Codex / product rules
  -> OpenAI Validator / taxonomy + prototype validation
  -> Account ChatGPT / implementation
  -> OpenAI Validator / QA acceptance
  -> Codex / release review
  -> Human / merge + production approval
```

Status: todo

Goal:
- define and implement multilingual Cambodia job/candidate matching;
- Khmer is the primary language, followed by English and Chinese;
- paid employer features must not directly increase relevance score;
- every match should expose reasons and confidence.

Acceptance:
- Codex documents matching/product rules and field definitions;
- OpenAI Validator validates Khmer taxonomy and prototype behavior;
- Account ChatGPT implements matching/API/data/tests;
- OpenAI Validator validates algorithm, multilingual UX and test evidence;
- Codex produces the release gate;
- production remains human-approved.

## GH-ISSUE-65 — Empty readiness check set

Status: todo

Goal:
- make `orchestrator.readiness.all_ok({})` return `False`; an empty set of
  readiness checks must not be treated as ready.

Implementation scope:
- `orchestrator/readiness.py` and `tests/test_readiness.py` only;
- add a regression test for the empty check set;
- preserve existing behavior for non-empty check sets;
- do not change API routes, secrets, deployment settings, payment logic,
  production data handling, or orchestration/model policy.

Acceptance and handoff sequence:
- OpenAI Validator prototype validation confirms the expected empty-set
  semantics and regression-test coverage;
- Account ChatGPT implements on the PR using the owner account ChatGPT 5.6 Sol
  High path; do not use the retired API Sol programmer;
- Work GPT-6 independently reviews the implementation, makes only targeted
  repairs if needed, and verifies CI against the exact final SHA before handing
  off to QA;
- OpenAI Validator QA confirms `all_ok({}) is False`, the existing readiness
  tests still pass, the new regression test passes, and the QA handoff is
  successful with no blockers;
- this task ends after QA; merge and deployment require separate explicit
  owner approval.
