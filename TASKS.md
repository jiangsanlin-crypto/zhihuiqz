# TASKS

## GH-ISSUE-65 — Empty readiness check set

Status: planned

Goal:
- make an empty readiness check set fail closed: `orchestrator.readiness.all_ok({})` returns `False`;
- preserve the existing result for non-empty check sets.

Scope:
- implementation in `orchestrator/readiness.py`;
- regression coverage in `tests/test_readiness.py`;
- no changes to API routes, secrets, deployment settings, payment logic,
  production data handling, or orchestration/model policy.

Acceptance and handoff gates:
- add a regression test for the empty check set and keep existing readiness
  tests passing;
- run CI against the exact final SHA before implementation handoff;
- use the owner account ChatGPT 5.6 Sol High implementation path;
- complete the mandatory Work GPT-6 code review and any targeted repair before
  GPT-6 Luna QA;
- require successful QA evidence before release review;
- this task's verification ends at QA; merge and deployment need separate
  explicit owner approval.

Risk: low. This changes only readiness-helper semantics and its unit coverage.

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
