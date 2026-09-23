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
        "workbuddy_runner": {
            "ok": bool(settings.workbuddy_url and settings.workbuddy_token),
            "detail": (
                "configured"
                if settings.workbuddy_url and settings.workbuddy_token
                else "missing URL or runner token"
            ),
        },
        "workbuddy_model": {
            "ok": (
                settings.workbuddy_model == "GLM-5.3-Flash"
                and settings.workbuddy_model_lock_confirmed
            ),
            "detail": {
                "expected": "GLM-5.3-Flash",
                "configured": settings.workbuddy_model,
                "lock_confirmed": settings.workbuddy_model_lock_confirmed,
            },
        },
        "openai_agent_execution": {
            "ok": True,
            "detail": (
                "Codex and ChatGPT run in GitHub Actions with hard-pinned "
                "model/effort values; OPENAI_API_KEY is validated by those workflows"
            ),
        },
    }


def all_ok(checks: dict[str, dict[str, Any]]) -> bool:
    return all(bool(item.get("ok")) for item in checks.values())
