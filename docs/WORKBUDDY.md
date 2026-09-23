# WorkBuddy Integration

WorkBuddy is the independent validation and deployment work body.

## GitHub access

WorkBuddy reads the public repository and PRs directly and receives no GitHub
write credential. Report write-back/dispatch is performed by the Orchestrator
after path and handoff validation.

## API authentication

The persistent WorkBuddy runner uses WorkBuddy OAuth/access-token credentials.

## Model lock

Required model: `GLM-5.3-Flash`.

The dedicated WorkBuddy/Buddy App must expose only that model. The Orchestrator
remains not-ready until `WORKBUDDY_MODEL_LOCK_CONFIRMED=true`.

## Prototype phase

Outputs:
- reports/prototype_review.md
- reports/data_analysis.md
- reports/classification_validation.md
- reports/uiux_prototype.md

Successful handoff -> ChatGPT.

## QA phase

Outputs:
- reports/test_report.md
- reports/uiux_acceptance.md
- reports/classification_validation.md
- reports/qa_summary.json

Successful handoff -> Codex release review.

## Deployment phase

After Codex marks the release ready, WorkBuddy performs an independent
production-readiness review.

Outputs:
- reports/deployment_plan.md
- reports/deployment_gate.json

A ready deployment gate automatically dispatches GitHub Actions to:
- wait required CI;
- merge the PR;
- deploy main;
- check health at 0/1/5/15 minutes;
- roll back on failure;
- mark the task done on success.

No per-release human approval is required when full-auto mode is enabled.
`EMERGENCY_STOP=true` stops the production stage before merge/deploy.
