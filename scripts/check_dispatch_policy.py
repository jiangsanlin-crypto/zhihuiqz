from pathlib import Path


def require(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment not in text:
            raise SystemExit(
                f"{path}: missing required dispatch-policy fragment: {fragment}"
            )


def forbid(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment in text:
            raise SystemExit(
                f"{path}: forbidden dispatch-policy fragment present: {fragment}"
            )


require(
    ".github/workflows/codex-task.yml",
    [
        "agent_codex_product",
        "agent_codex_release",
        'event_type:"agent_workbuddy_prototype"',
        'event_type:"agent_workbuddy_deploy"',
    ],
)

require(
    ".github/workflows/openai-validator.yml",
    [
        "agent_workbuddy_prototype",
        "agent_workbuddy_qa",
        "agent_workbuddy_deploy",
        "pull_request:",
        "types: [labeled]",
        "agent_codex_release",
        "agent_execute_deployment",
        'NEXT_EVENT=""',
        'PREV_FROM="workreview"',
        'PREV_HANDOFF_PHASE="code_review"',
    ],
)

require(
    ".github/workflows/bootstrap-labels.yml",
    [
        'agent:workreview',
        'phase:code-review',
    ],
)

forbid(
    ".github/workflows/openai-validator.yml",
    [
        "agent_chatgpt_implementation",
    ],
)

require(
    ".github/workflows/chatgpt-dev.yml",
    [
        "ChatGPT Implementation (API Retired)",
        "API Sol worker is retired",
    ],
)

forbid(
    ".github/workflows/chatgpt-dev.yml",
    [
        "repository_dispatch:",
        "agent_chatgpt_implementation",
        "agent_workbuddy_qa",
        "openai/codex-action",
    ],
)

require(
    ".github/workflows/auto-production-deploy.yml",
    [
        "types: [agent_execute_deployment]",
        "gh pr merge",
        "status:deployed",
        "status:done",
    ],
)

if Path(".github/workflows/route-task.yml").exists():
    raise SystemExit("legacy persistent WorkBuddy route workflow must be absent")

print("account-backed implementation dispatch chain validated")
