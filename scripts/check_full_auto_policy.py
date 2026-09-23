from pathlib import Path


def require(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment not in text:
            raise SystemExit(
                f"{path}: missing full-auto policy fragment: {fragment}"
            )


require(
    "config/automation_policy.json",
    [
        '"auto_production_enabled": true',
        '"emergency_stop": false',
        '"require_ci_check": "test"',
    ],
)

require(
    ".github/workflows/auto-production-deploy.yml",
    [
        "Require autonomous production controls",
        "config/automation_policy.json",
        "Validate WorkBuddy deployment handoff",
        "Validate release and deployment gates",
        "Wait for CI test check",
        "Merge approved-by-policy PR",
        "Deploy main and verify 0m 1m 5m 15m health",
        "Rolling back",
    ],
)

require(
    "orchestrator/workbuddy_runner.py",
    [
        "DEPLOY_FILES",
        "deployment_plan.md",
        "deployment_gate.json",
        'req.phase == "phase:deploy"',
        'phase="deployment_plan"',
    ],
)

print("full-auto production policy validated")
