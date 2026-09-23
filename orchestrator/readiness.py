from __future__ import annotations

from typing import Any

from .config import Settings

EXPECTED_MODEL = "GLM-5.3-Flash"


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
                settings.workbuddy_model == EXPECTED_MODEL
                and settings.workbuddy_model_lock_confirmed
            ),
            "detail": {
                "expected": EXPECTED_MODEL,
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


def workbuddy_live_check(
    health: dict[str, Any],
) -> tuple[dict[str, Any], str, bool]:
    configured = bool(
        health.get("workbuddy_configured", health.get("oauth_configured"))
    )
    mode = "full" if configured else "degraded"
    model_ok = (
        health.get("expected_model") == EXPECTED_MODEL
        and bool(health.get("model_lock_confirmed"))
    )
    runner_ok = bool(health.get("ok"))

    detail = {
        key: value
        for key, value in health.items()
        if key not in {"token", "access_token", "refresh_token"}
    }
    detail.update(
        {
            "workbuddy_mode": mode,
            "workbuddy_configured": configured,
            "real_dispatch_enabled": configured,
        }
    )
    if not configured:
        detail["reason"] = (
            "OAuth is optional for bootstrap; real WorkBuddy cloud dispatch "
            "is disabled until credentials are added and the runner restarts."
        )

    return {
        "ok": runner_ok and model_ok,
        "detail": detail,
    }, mode, configured


def all_ok(checks: dict[str, dict[str, Any]]) -> bool:
    return all(bool(item.get("ok")) for item in checks.values())
