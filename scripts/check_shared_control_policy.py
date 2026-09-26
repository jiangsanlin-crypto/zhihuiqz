from pathlib import Path


def text(path: str) -> str:
    return Path(path).read_text()


def require(path: str, fragments: list[str]) -> None:
    value = text(path)
    for fragment in fragments:
        if fragment not in value:
            raise SystemExit(f"{path}: missing shared-control policy fragment: {fragment}")


def forbid(path: str, fragments: list[str]) -> None:
    value = text(path)
    for fragment in fragments:
        if fragment in value:
            raise SystemExit(f"{path}: forbidden shared-control bypass fragment: {fragment}")


require(
    "orchestrator/control_service.py",
    [
        "async def dispatch_loop",
        "await dispatch_ready(store, github, settings, build_sha)",
        "native_queue=False",
        '"agents_enabled": False',
        '"protocol": "shared-claims:v1"',
    ],
)

require(
    "orchestrator/control_dispatch.py",
    [
        "shared_codex_product",
        "shared_codex_resume",
        "shared_validator_prototype",
        "shared_validator_qa",
        "DISPATCH_COOLDOWN_SECONDS",
        "store.operation_active(operation_key)",
    ],
)

require(
    ".github/workflows/account-worker-control.yml",
    [
        "issue_comment:",
        "github.event.comment.user.login == github.repository_owner",
        'EXPECTED_CONTROL_SHA="$(git rev-parse HEAD)"',
        "scripts/account_worker_broker.py",
        "<!-- shared-control-result:v1 -->",
    ],
)
forbid(
    ".github/workflows/account-worker-control.yml",
    ["gh issue edit", "gh pr edit", "--add-label", "--remove-label"],
)

require(
    "scripts/account_worker_broker.py",
    [
        "ensure_controller_identity",
        'identity.get("build_sha") != EXPECTED_CONTROL_SHA',
        'control_request("POST", "/claims/acquire"',
        'control_request("POST", "/claims/start"',
        'control_request("POST", "/claims/advance"',
        'control_request("POST", "/claims/decision"',
    ],
)
forbid(
    "scripts/account_worker_broker.py",
    ["set_labels(", "gh issue edit", "gh pr edit"],
)

require(
    ".github/workflows/shared-agent-runtime.yml",
    [
        "shared_codex_product",
        "shared_codex_resume",
        "shared_validator_prototype",
        "shared_validator_qa",
        "/claims/acquire",
        "/claims/start",
        "/claims/publish-reports",
        "/claims/advance",
        "Wait for exact current-SHA ordinary CI",
        "owner_approval_required",
        "release_enabled=false",
    ],
)
forbid(
    ".github/workflows/shared-agent-runtime.yml",
    ["gh pr merge", "agent_execute_deployment", "status:done"],
)

require(
    ".github/workflows/start-agent-task.yml",
    [
        "shared_workflow_entry.py --source planner",
        "Machine chain ends at exact-SHA Human Approval",
    ],
)
forbid(
    ".github/workflows/start-agent-task.yml",
    ["--add-label", "--remove-label", 'event_type:"agent_codex_product"'],
)

require(
    ".github/workflows/e2e-smoke.yml",
    [
        "Wait for canonical Human Approval",
        "approval:production-required",
        "validate_handoff.py",
        "--require-independent-review",
        "No merge or deployment was performed",
    ],
)
forbid(
    ".github/workflows/e2e-smoke.yml",
    ["gh pr merge", "agent_execute_deployment"],
)

for path in [
    ".github/workflows/openai-validator.yml",
    ".github/workflows/codex-task.yml",
    ".github/workflows/handoff-reconciler.yml",
    ".github/workflows/agent-watchdog.yml",
]:
    require(
        path,
        [
            "vars.CONTROL_WORKFLOW_MODE == ''",
            "vars.CONTROL_WORKFLOW_MODE == 'shared'",
            "vars.CONTROL_WORKFLOW_MODE == 'legacy'",
            "github.event.repository.default_branch",
            "git rev-parse HEAD",
            "shared_workflow_entry.py",
        ],
    )

require(
    "config/automation_policy.json",
    [
        '"require_owner_approval": true',
        '"synthetic_e2e_never_deploys": true',
    ],
)

print("shared-controller full-auto policy validated")
