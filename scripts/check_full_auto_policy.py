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
        '"require_owner_approval": true',
        '"synthetic_e2e_never_deploys": true',
    ],
)

require(
    ".github/workflows/openai-validator.yml",
    [
        "reports/prototype_gate.json",
        "reports/qa_summary.json",
        "reports/deployment_gate.json",
        "Run deterministic QA tests",
        "Resolve QA terminal policy",
        "approval:production-required",
        "terminal-policy:v1",
        '--trusted-login "${{ github.repository_owner }}"',
        '--trusted-login "github-actions[bot]"',
    ],
)


require(
    ".github/workflows/codex-task.yml",
    [
        "Require release-enabled terminal policy or exact owner release approval",
        "release-approval:v1",
        "Hold release in owner review",
    ],
)

require(
    ".github/workflows/auto-production-deploy.yml",
    [
        "Require autonomous production controls",
        "Validate OpenAI validator deployment handoff",
        "Validate release and deployment gates",
        "Require exact-head CI",
        "Require exact-SHA owner production approval",
        "approval:production-approved",
        "production-approval:v1",
        "Run final repository tests before merge",
        "Recheck immutable merge inputs",
        "Merge exact approved PR head",
        '--match-head-commit "$SOURCE_SHA"',
        "Resolve exact merge commit",
        "Deploy exact merge commit and verify 0m 1m 5m 15m health",
        "production-deploy-${{ github.repository }}",
        "ORIGIN_MAIN",
        "Rolling back",
    ],
)

require(
    "orchestrator/handoff_gate.py",
    [
        "trusted_logins",
        "_comment_login",
        "Trust is established before parsing",
    ],
)

require(
    "scripts/reconcile_handoff_state.py",
    [
        "intentional_owner_wait",
        "blocked_requires_recovery",
    ],
)


require(
    ".github/workflows/agent-watchdog.yml",
    [
        "Redispatch queued API-owned phases with bounded idempotency",
        "Recover watchdog timeout blockers with bounded retry and escalation",
        "agent-watchdog:redispatch",
        "agent-watchdog:auto-retry",
        "Reclaim orphaned exact-SHA Work review",
        "scripts/plan_review_reclaim.py",
        "phase:escalation-repair",
        "Requeue exact-SHA technical failures with bounded budget",
        "recovery:technical",
        "agent-watchdog:technical-retry",
    ],
)

require(
    ".github/workflows/bootstrap-labels.yml",
    [
        'phase:escalation-repair',
        'recovery:technical',
    ],
)

require(
    "orchestrator/state_store.py",
    [
        "recover_interrupted",
        "recovered after orchestrator restart",
        "WHERE status='running'",
    ],
)

print("full-auto production safety policy validated")
