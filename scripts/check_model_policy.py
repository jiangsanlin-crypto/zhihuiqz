from pathlib import Path


def require(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment not in text:
            raise SystemExit(
                f"{path}: missing required model-policy fragment: {fragment}"
            )


def forbid(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment in text:
            raise SystemExit(
                f"{path}: retired/forbidden model-policy fragment still present: {fragment}"
            )


require(
    ".github/workflows/codex-task.yml",
    [
        "model: gpt-5.6-luna",
        "effort: high",
    ],
)

require(
    ".github/workflows/openai-validator.yml",
    [
        "model: gpt-5.6-luna",
        "effort: high",
        "pull_request:",
        "types: [labeled]",
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
        "openai/codex-action",
        "OPENAI_API_KEY",
        "model: gpt-5.6-sol",
        "agent_chatgpt_implementation",
    ],
)

require(
    "agents/chatgpt_prompt.md",
    [
        "ordinary Chat worker",
        "GPT-5.6 Sol",
        "Reasoning level: High",
        "repository API-backed Sol workflow is retired",
    ],
)

require(
    "agents/workbuddy_prompt.md",
    [
        "No WorkBuddy OAuth or WorkBuddy Cloud dependency",
        "Runtime model: `gpt-5.6-luna`",
    ],
)

print("account-backed implementation and API Luna model policy validated")
