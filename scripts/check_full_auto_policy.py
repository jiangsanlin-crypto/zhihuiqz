from pathlib import Path


def require(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment not in text:
            raise SystemExit(
                f"{path}: missing full-auto policy fragment: {fragment}"
            )


require(
    ".github/workflows/repository-hardening.yml",
    [
        '"required_approving_review_count": 0',
        '"require_code_owner_reviews": false',
        '"allow_force_pushes": false',
        '"allow_deletions": false',
        '"enforce_admins": true',
    ],
)

require(
    ".github/workflows/auto-production-deploy.yml",
    [
        'test "$AUTO_PRODUCTION_ENABLED" = "true"',
        'test "${EMERGENCY_STOP:-false}" != "true"',
        "Validate WorkBuddy deployment handoff",
        "Validate release and deployment gates",
        "Wait for required PR checks",
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
