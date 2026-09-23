# WorkBuddy Integration

WorkBuddy is the independent validation/deployment work body.

## GitHub access

The repository and task PRs are public.

WorkBuddy reads them directly and receives no GitHub token, GitHub OAuth grant,
or GitHub connector authorization.

All report write-back is performed by the Orchestrator after strict path
validation.

## WorkBuddy API authentication

The persistent WorkBuddy runner needs WorkBuddy's own OAuth credentials:
- WORKBUDDY_CLIENT_ID
- WORKBUDDY_CLIENT_SECRET
- WORKBUDDY_REFRESH_TOKEN

A temporary WORKBUDDY_ACCESS_TOKEN can be used during bootstrap.

## Model lock

Required model: `GLM-5.3-Flash`.

The Cloud Task create endpoint does not expose a per-task model parameter.
Therefore enforcement is at the dedicated WorkBuddy/Buddy App configuration:

1. expose GLM-5.3-Flash only;
2. set it as default;
3. verify no Auto/alternate model is selectable;
4. set WORKBUDDY_MODEL=GLM-5.3-Flash;
5. set WORKBUDDY_MODEL_LOCK_CONFIRMED=true only after verification.

The Orchestrator remains not-ready until this is confirmed.

## Prototype phase

WorkBuddy reads Codex planning outputs and returns only the allowed reports:
- reports/prototype_review.md
- reports/data_analysis.md
- reports/classification_validation.md
- reports/uiux_prototype.md

Successful handoff goes to ChatGPT.

## QA phase

The WorkBuddy runner first executes deterministic Git/Python checks in an
isolated temporary workspace, then asks WorkBuddy to perform classification,
multilingual UI and UI/UX acceptance.

Allowed outputs:
- reports/test_report.md
- reports/uiux_acceptance.md
- reports/classification_validation.md
- reports/qa_summary.json

Successful handoff goes to Codex release review.

## Deployment phase

WorkBuddy owns deployment review, health verification and rollback decisions.
GitHub Actions performs the actual SSH/Docker commands after human approval.

See docs/DEPLOYMENT_HANDOFF.md.
