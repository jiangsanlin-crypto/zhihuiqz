from pathlib import Path


def require(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment not in text:
            raise SystemExit(
                f"{path}: missing required dispatch-policy fragment: {fragment}"
            )


require(
    ".github/workflows/codex-task.yml",
    [
        "agent_codex_product",
        "agent_codex_release",
        'event_type:"agent_workbuddy_prototype"',
        'event_type:"agent_workbuddy_deploy"',
        'phase:"prototype"',
        'phase:"deploy"',
    ],
)

require(
    ".github/workflows/chatgpt-dev.yml",
    [
        "repository_dispatch:",
        "types: [agent_chatgpt_implementation]",
        'event_type:"agent_workbuddy_qa"',
        'phase:"qa"',
    ],
)

require(
    ".github/workflows/route-task.yml",
    [
        "agent_workbuddy_prototype",
        "agent_workbuddy_qa",
        "agent_workbuddy_deploy",
        "Relay WorkBuddy event to persistent Orchestrator",
        "runtime_secret.py ORCHESTRATOR_TOKEN",
    ],
)

require(
    "orchestrator/main.py",
    [
        '"agent_chatgpt_implementation"',
        '"agent_codex_release"',
        '"agent_execute_deployment"',
        "repository_dispatch(",
    ],
)

require(
    ".github/workflows/auto-production-deploy.yml",
    [
        "types: [agent_execute_deployment]",
        "config/automation_policy.json",
        "gh pr merge",
        "status:deployed",
        "status:done",
    ],
)

print("repository-dispatch chain validated")
