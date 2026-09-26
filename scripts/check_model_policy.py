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
        "model: gpt-6-luna",
        "effort: high",
    ],
)

require(
    ".github/workflows/openai-validator.yml",
    [
        "model: gpt-6-luna",
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
        "openai-api-key:",
        "secrets.OPENAI_API_KEY",
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
        "to_agent: workreview",
        "agent:workreview",
        "phase:code-review",
    ],
)

require(
    "agents/workreview_prompt.md",
    [
        "Target model: GPT-6 in Work",
        "Logical handoff ID: `workreview`",
        "to_agent: `workbuddy`",
        "phase: `code_review`",
    ],
)

require(
    "agents/workbuddy_prompt.md",
    [
        "No WorkBuddy OAuth or WorkBuddy Cloud dependency",
        "Runtime model: `gpt-6-luna`",
    ],
)

print("account-backed implementation and API Luna model policy validated")


require(
    ".github/workflows/handoff-reconciler.yml",
    [
        "issue_comment:",
        'cron: "*/5 * * * *"',
        "scripts/reconcile_handoff_state.py",
        "--ci-runs-json",
        "labels_after",
        "agent_workbuddy_qa",
        "ensure_qa_dispatch",
        "agent-handoff-qa-dispatch:v1",
        "converge_owner_wait",
    ],
)

require(
    "scripts/reconcile_handoff_state.py",
    [
        '("chatgpt", "workreview", "implementation")',
        '("workreview", "workbuddy", "code_review")',
        "current_sha_ci_not_success",
        "canonical_qa_may_need_dispatch",
        "converge_owner_wait",
        "missing_independent_current_sha_review_pass",
        "validated_timeout_resolved",
    ],
)

require(
    ".github/workflows/openai-validator.yml",
    [
        "--require-independent-review",
        '--paginate --jq',
        'head_sha == $sha',
        "steps.context.outputs.source_sha",
        "Pin trusted gate code from the default branch",
        "PYTHONPATH=\"$RUNNER_TEMP/trusted\"",
    ],
)
