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

Status: planned; prototype validation is next.

Goal:
- make `orchestrator.readiness.all_ok({})` return `False`, so an absent set of
  readiness checks cannot be treated as ready.

Scope:
- implement the behavior in `orchestrator/readiness.py`;
- add the focused empty-set regression test in `tests/test_readiness.py`;
- preserve existing behavior for every non-empty check set;
- leave routes, secrets, deployment settings, payment behavior, production data
  handling, and model/orchestration policy unchanged.

Acceptance:
- `all_ok({}) is False`;
- existing readiness tests and the new regression test pass;
- CI passes for the exact final PR head SHA;
- implementation is performed by Account ChatGPT 5.6 Sol High, followed by
  mandatory Work GPT-6 code review and OpenAI Validator QA;
- this task stops after successful QA and does not authorize merge or deploy.
