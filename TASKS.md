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

## GH-ISSUE-86 — Shared exact-SHA automation acceptance

Status: todo

Goal:
- validate the complete shared-controller automation chain on one clean,
  synthetic task;
- verify task, PR and source-SHA binding at every handoff and evidence-based
  transition.

Constraints:
- use synthetic data only; do not use production data;
- do not merge or deploy this synthetic task;
- terminal policy is `owner_approval_required`.

Required machine chain:
1. Codex product planning;
2. OpenAI Validator (`workbuddy`) prototype, data and classification
   validation;
3. Account Chat implementation, which creates
   `tests/agent_e2e_marker.txt` with exactly `AGENT_E2E_OK` and no trailing
   newline;
4. independent Work Review;
5. OpenAI Validator QA;
6. if QA changes HEAD, run CI for that exact new SHA, obtain a new independent
   Work Review for that SHA, then run evidence-only final QA against that SHA;
7. stop at Human Approval.

Acceptance:
- each handoff and evidence-dependent transition matches this task and the
  current PR head SHA, reports success and has no blockers;
- when QA changes HEAD, no prior-SHA CI, review or QA evidence is carried
  forward;
- terminal labels include `status:review` and
  `approval:production-required`, with no active `agent:*`, `phase:*`,
  `status:todo`, `status:running` or `status:blocked` labels;
- the synthetic task stops at Human Approval and is not merged or deployed.
