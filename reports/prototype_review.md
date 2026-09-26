# Prototype validation — GH-ISSUE-19

**Decision:** Ready for the synthetic handoff implementation, within the scope below.

## Binding and evidence

- Task: `GH-ISSUE-19`
- PR: `#90`
- Planning source SHA: `60cfb96ecdd9604d9e6e91aae704d3fdb82d6d22`
- Prior handoff: `codex` → `workbuddy`, phase `product_planning`, status `success`, blockers empty, exact source SHA matched. The shared controller reports that it validated this binding before this run.
- Planning artifacts define a coordination-only synthetic notification/handoff check. They do not specify a recruitment product prototype.

## Implementability and acceptance

The task is implementable as a bounded workflow exercise. Keep any implementation artifact or payload synthetic. Each stage must retain `GH-ISSUE-19`, the expected phase and agent identities, PR #90, and the exact current head SHA. A changed head invalidates prior SHA-bound evidence; the responsible stages must publish fresh evidence before advancement.

`TASKS.md` omits the independent WorkReview step. The canonical sequence in `AGENTS.md` requires Work GPT-6 code review between account ChatGPT implementation and Validator QA. Keep that review in the exercised route and capture its exact-SHA handoff; the task-specific abbreviated sequence does not waive it. End this synthetic chain at Human Approval. Do not merge, deploy, or process real candidate or payment data.

Use the approved shared-control path and its cooperative executor for this task. Workflow state belongs to the controller's acquire/start/heartbeat/advance interfaces. Preserve the repository/PR/SHA binding, stop if ownership is lost, and publish trusted handoff evidence before requesting advancement. Do not let a callback run a nested legacy workflow or dispatch a second agent chain. A wake-up alone is not phase-completion evidence. The fixed validator runtime is `gpt-6-luna` / high; do not use WorkBuddy Cloud, OAuth, fallback models, direct production SSH, or a legacy state writer.

Repository evidence describes an exact-SHA synthetic acceptance route that includes independent review, QA, and a terminal Human Approval state (`.github/workflows/e2e-smoke.yml`, `docs/worker-rollout-gates.md`). This supports the feasibility of the bounded route. The route has not been executed as part of prototype review: no end-to-end notification or implementation result is claimed here.

## Scope boundary

This decision covers the coordination test only. The planning artifacts do not include PRD, recruitment rules, data-collection plan, classification dictionary, or a UI prototype. Consequently, this report does not approve recruitment matching behavior or any Khmer taxonomy, candidate/job fields, or user-facing product screen. See the accompanying data, classification, and UI/UX reports for those limits.

## Required implementation evidence

- Preserve task, PR, phase, ownership, and exact-SHA binding at every handoff.
- Include the mandatory independent WorkReview stage before Validator QA.
- Use only synthetic notification content; do not put secrets or personal data in logs or handoff payloads.
- Require each completed stage to report success with no blockers before advancing.
- Stop at Human Approval and leave merge/deployment unperformed.
- Do not describe this prototype gate as proof that notifications were delivered or that the full chain passed.
