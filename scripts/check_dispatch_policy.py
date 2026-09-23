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
    ],
)

require(
    ".github/workflows/openai-validator.yml",
    [
        "agent_workbuddy_prototype",
        "agent_workbuddy_qa",
        "agent_workbuddy_deploy",
        "agent_chatgpt_implementation",
        "agent_codex_release",
        "agent_execute_deployment",
    ],
)

require(
    ".github/workflows/chatgpt-dev.yml",
    [
        "types: [agent_chatgpt_implementation]",
        'event_type:"agent_workbuddy_qa"',
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

print("OpenAI-only repository-dispatch chain validated")
