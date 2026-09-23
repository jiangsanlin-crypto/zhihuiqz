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

env_text = Path(".env.example").read_text()
if "WORKBUDDY_MODEL=GLM-5.3-Flash" not in env_text:
    raise SystemExit("WorkBuddy model pin is missing")
if "WORKBUDDY_MODEL_LOCK_CONFIRMED=false" not in env_text:
    raise SystemExit("WorkBuddy model-lock confirmation guard is missing")

print("strict model policy validated")
