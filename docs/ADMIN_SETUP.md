# Repository Administration Setup

## Full-auto main protection

Configure `REPO_ADMIN_TOKEN` as a narrowly scoped repository administration
credential, then run `Configure Main Protection` with `PROTECT-MAIN`.

The workflow configures:
- PR required for main;
- required `test` CI context;
- zero required human approvals for policy-gated automation;
- CODEOWNERS review not required for normal auto delivery;
- conversation resolution;
- force-push disabled;
- branch deletion disabled;
- admin enforcement enabled.

## Automation identity

`AGENT_GITHUB_TOKEN` must be separate from `REPO_ADMIN_TOKEN`.

It needs repository-scoped:
- Contents read/write;
- Issues read/write;
- Pull requests read/write;
- Metadata read.

Do not give it branch-protection bypass or unrelated repository access.

## Full-auto controls

Configure:
- `AUTO_PRODUCTION_ENABLED=true`
- `EMERGENCY_STOP=false`

Set `EMERGENCY_STOP=true` at any time to stop new automatic production
execution.

## WorkBuddy

The dedicated WorkBuddy app must expose only `GLM-5.3-Flash` before
`WORKBUDDY_MODEL_LOCK_CONFIRMED=true` is set on the server.

## Activation

Run readiness -> bootstrap Orchestrator -> postdeploy readiness -> E2E. After
that, `Start Agent Task` can drive the chain to deployment without a human
handoff.
