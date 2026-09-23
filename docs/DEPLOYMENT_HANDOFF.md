# WorkBuddy Deployment Handoff

Deployment owner: **WorkBuddy**  
Command executor: **GitHub Actions**

Normal product releases do not wait for a per-release human approval.

## Deployment gate

After Codex release review succeeds, WorkBuddy reads the public PR, QA reports,
release gate, release notes, Docker/deployment documentation and prior handoffs.

Required outputs:
- `reports/deployment_plan.md`
- `reports/deployment_gate.json`

The gate must be `ready` before execution.

## Execution

After the WorkBuddy gate succeeds, the Orchestrator dispatches:

`agent_execute_deployment`

The deployment workflow then:
- checks `AUTO_PRODUCTION_ENABLED=true`;
- checks `EMERGENCY_STOP != true`;
- waits for required PR checks;
- merges the PR;
- deploys main to the configured persistent server;
- checks `/readyz` at 0m, 1m, 5m and 15m;
- rolls back to the previous server SHA on failure;
- marks the PR/task `status:deployed` and `status:done` on success.

## One-time activation

The first Orchestrator bootstrap and repository administration still require
account/secrets setup. Once activation is complete, normal task delivery is
fully automatic.

## Emergency stop

Set GitHub secret:

`EMERGENCY_STOP=true`

to stop new automatic production executions before merge/deploy.

To re-enable, set it to `false` after the incident is resolved.

## Scope boundary

Automatic deployment permission covers repository software delivery. It does
not automatically authorize real payment execution or onboarding/processing of
real candidate production data.
