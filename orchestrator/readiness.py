from __future__ import annotations

from typing import Any

from .config import Settings


def static_checks(settings: Settings) -> dict[str, dict[str, Any]]:
    checks = {
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
        "sandbox_runner": {
            "ok": bool(settings.sandbox_url and settings.sandbox_token),
            "detail": (
                "configured"
                if settings.sandbox_url and settings.sandbox_token
                else "missing URL or runner token"
            ),
        },
        "codex_execution": {
            "ok": True,
            "detail": "GitHub Actions mode; OPENAI_API_KEY is validated by the workflow",
        },
    }
    return checks


def all_ok(checks: dict[str, dict[str, Any]]) -> bool:
    return all(bool(item.get("ok")) for item in checks.values())
