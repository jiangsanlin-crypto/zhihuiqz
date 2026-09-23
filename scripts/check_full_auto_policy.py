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
    ".github/workflows/openai-validator.yml",
    [
        "reports/prototype_gate.json",
        "reports/qa_summary.json",
        "reports/deployment_gate.json",
        "Run deterministic QA tests",
    ],
)

require(
    ".github/workflows/auto-production-deploy.yml",
    [
        "Require autonomous production controls",
        "Validate OpenAI validator deployment handoff",
        "Validate release and deployment gates",
        "Run final repository tests before merge",
        "Merge approved-by-policy PR",
        "Deploy main and verify 0m 1m 5m 15m health",
        "Rolling back",
    ],
)

print("full-auto production policy validated")
