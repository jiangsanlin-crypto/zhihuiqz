from __future__ import annotations

import os
from dataclasses import dataclass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("APP_PORT", "8080"))
    state_db: str = os.getenv("STATE_DB", "./data/orchestrator.db")

    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_repository: str = os.getenv("GITHUB_REPOSITORY", "")
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    orchestrator_token: str = os.getenv("ORCHESTRATOR_TOKEN", "")

    workbuddy_url: str = os.getenv("WORKBUDDY_URL", "")
    workbuddy_token: str = os.getenv("WORKBUDDY_TOKEN") or os.getenv("ORCHESTRATOR_TOKEN", "")
    workbuddy_model: str = os.getenv("WORKBUDDY_MODEL", "GLM-5.3-Flash")
    workbuddy_model_lock_confirmed: bool = env_bool(
        "WORKBUDDY_MODEL_LOCK_CONFIRMED",
        False,
    )

    max_retries: int = int(os.getenv("MAX_RETRIES", "6"))


settings = Settings()
