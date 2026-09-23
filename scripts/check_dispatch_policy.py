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
        "repository_dispatch:",
        "types: [agent_codex_release]",
        'event_type:"agent_workbuddy_prototype"',
        'phase:"prototype"',
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
        "Relay WorkBuddy event to persistent Orchestrator",
    ],
)

require(
    "orchestrator/main.py",
    [
        '"agent_chatgpt_implementation"',
        '"agent_codex_release"',
        "repository_dispatch(",
    ],
)

print("repository-dispatch chain validated")
