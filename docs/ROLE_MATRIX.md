# Three Work-Body Responsibility Matrix

## Codex

Owns product management, Cambodia recruitment rules, taxonomy, collection
planning, task acceptance criteria, release review and release notes.

It does not implement primary application code or execute server commands.

## ChatGPT

Owns frontend/backend implementation, classification engineering, data/API/
database changes, migrations and tests.

It does not self-approve product rules or execute production deployment.

## WorkBuddy

Owns prototype validation, data analysis, classification validation, QA,
multilingual/UI/UX acceptance, deployment planning, production readiness,
post-deployment health interpretation and rollback policy.

Actual SSH/Docker execution is performed by GitHub Actions.

## Automation control plane

GitHub Actions + Orchestrator perform deterministic routing, merge, deployment,
health checks and rollback.

Normal product software delivery is fully automatic once
`AUTO_PRODUCTION_ENABLED=true`.

## Human owner

The human owner configures account-level credentials, may activate
`EMERGENCY_STOP`, and can intervene on blocked incidents.

Separate explicit authorization is still required before agents may perform
real payment transactions or use real candidate production data.
