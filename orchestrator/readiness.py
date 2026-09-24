from __future__ import annotations

from typing import Any

from .config import Settings


def static_checks(settings: Settings) -> dict[str, dict[str, Any]]:
    return {
        "github_repository": {
            "ok": bool(settings.github_repository),
            "detail": "configured" if settings.github_repository else "missing",
        },
        "github_write_token": {
            "ok": bool(settings.github_token),
            "detail": "configured" if settings.github_token else "missing",
        },
        "orchestrator_token": {
            "ok": bool(settings.orchestrator_token),
            "detail": "configured" if settings.orchestrator_token else "missing",
        },
        "openai_agent_execution": {
            "ok": True,
            "detail": (
                "Codex, ChatGPT and the validation agent execute in GitHub "
                "Actions using OPENAI_API_KEY; WorkBuddy Cloud is not required"
            ),
        },
    }


def all_ok(checks: dict[str, dict[str, Any]]) -> bool:
    return all(bool(item.get("ok")) for item in checks.values())


def failed_check_names(checks: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(name for name, item in checks.items() if not bool(item.get("ok")))
