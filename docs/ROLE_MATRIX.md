# Three Work-Body Responsibility Matrix

## Codex

Owns product management, recruitment rules, taxonomy, collection planning,
acceptance criteria, release review and release notes.

Runtime: `gpt-5.6-luna` / max.

## ChatGPT

Owns frontend/backend implementation, classification engineering, APIs/data,
migrations and tests.

Runtime: `gpt-5.6-sol` / high.

## OpenAI Validation Agent

Owns independent prototype validation, data-assumption review, classification
validation, deterministic QA review, multilingual UI/UX acceptance and
deployment-readiness review.

Runtime: `gpt-5.6-luna` / high.

Compatibility agent ID: `workbuddy`.

It does not use WorkBuddy Cloud or WorkBuddy OAuth.

## Automation control plane

GitHub Actions performs routing, handoff validation, test gates, merge,
deployment, health checks and rollback.

The human owner can intervene on blocked incidents and control the repository
emergency-stop policy.
