# OpenAI Validator Deployment Handoff

Deployment-readiness owner: **OpenAI Validator**  
Compatibility handoff/label ID: **workbuddy**  
Command executor: **GitHub Actions**

No WorkBuddy Cloud, WorkBuddy OAuth or external WorkBuddy runner participates.

## Deployment gate

After Codex release review succeeds, OpenAI Validator reads the PR, QA reports,
release gate, release notes, deployment documentation and prior handoffs.

Required outputs:
- `reports/deployment_plan.md`
- `reports/deployment_gate.json`

The gate must be `ready` before deterministic execution.

## Execution

After the Validator gate succeeds, GitHub Actions receives
`agent_execute_deployment` and:
- checks the repository production-enable policy;
- checks emergency stop;
- waits for required PR checks;
- merges only when all policy gates permit it;
- deploys main to the configured server;
- performs health verification;
- rolls back on failed readiness;
- marks the task deployed/done only on success.

## Scope boundary

Software-delivery automation does not authorize real payment execution or
onboarding/processing of real candidate production data.
