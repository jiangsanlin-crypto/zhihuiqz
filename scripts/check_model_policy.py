from pathlib import Path


def require(path: str, fragments: list[str]) -> None:
    text = Path(path).read_text()
    for fragment in fragments:
        if fragment not in text:
            raise SystemExit(
                f"{path}: missing required model-policy fragment: {fragment}"
            )


require(
    ".github/workflows/chatgpt-dev.yml",
    [
        "model: gpt-5.6-sol",
        "effort: high",
    ],
)

require(
    ".github/workflows/codex-task.yml",
    [
        "model: gpt-5.6-luna",
        "effort: max",
    ],
)

require(
    ".github/workflows/openai-validator.yml",
    [
        "model: gpt-5.6-luna",
        "effort: high",
        "No WorkBuddy OAuth or WorkBuddy Cloud dependency",
    ],
)

print("strict OpenAI-only model policy validated")
