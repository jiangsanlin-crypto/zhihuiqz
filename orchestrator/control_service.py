"""Standalone shared queue/claim controller. No model executor is loaded."""
import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .claim_api import create_claim_router
from .control_api import create_control_router
from .control_dispatch import dispatch_ready
from .github_client import GitHubClient
from .issue_intake import create_intake_router
from .queue_discovery import discovery_loop
from .state_store import StateStore


def secret_file(path) -> str:
    """Read a dedicated controller credential file without accepting multiline data."""
    value = Path(path).read_text().strip()
    if len(value) < 32 or any(c.isspace() for c in value):
        raise ValueError("invalid control-service credential file")
    return value


def secret_value(path: str, env_name: str) -> str:
    """Prefer a mounted secret file; fall back to the protected server env."""
    candidate = Path(path)
    if candidate.exists():
        return secret_file(candidate)
    value = os.environ.get(env_name, "").strip()
    if len(value) < 20 or any(c.isspace() for c in value):
        raise ValueError(f"invalid controller credential: {env_name}")
    return value


def create_app(*, store=None, github=None, settings=None, writes_enabled=None, build_sha=None):
    if settings is None:
        repository = (
            os.environ.get("CONTROL_REPOSITORY", "").strip()
            or os.environ.get("GITHUB_REPOSITORY", "").strip()
        )
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("CONTROL_REPOSITORY is required")
        settings = SimpleNamespace(
            github_repository=repository,
            orchestrator_token=secret_value(
                "/run/secrets/control_token", "ORCHESTRATOR_TOKEN"
            ),
        )
        github = GitHubClient(
            secret_value("/run/secrets/control_github_token", "GITHUB_TOKEN")
        )
        store = StateStore(
            os.environ.get("CONTROL_STATE_DB", "").strip()
            or os.environ.get("STATE_DB", "").strip()
            or "/state/control.db"
        )
    if writes_enabled is None:
        writes_enabled = os.environ.get("CONTROL_WRITES_ENABLED", "false").lower() == "true"
    build_sha = build_sha or os.environ.get("CONTROL_BUILD_SHA", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", build_sha):
        raise ValueError("CONTROL_BUILD_SHA must identify the reviewed commit")

    async def dispatch_loop(stop):
        while not stop.is_set():
            try:
                await dispatch_ready(store, github, settings, build_sha)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "controller dispatch deferred: %s", type(exc).__name__
                )
            try:
                await asyncio.wait_for(stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()
        tasks = []
        if writes_enabled:
            tasks = [
                asyncio.create_task(
                    discovery_loop(
                        stop,
                        store,
                        github,
                        settings.github_repository,
                        native_queue=False,
                    )
                ),
                asyncio.create_task(dispatch_loop(stop)),
            ]
        try:
            yield
        finally:
            stop.set()
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(
        lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.middleware("http")
    async def read_only_preflight(request: Request, call_next):
        if not writes_enabled and request.method not in {"GET", "HEAD"}:
            return JSONResponse({"detail": "CONTROL_WRITES_DISABLED"}, status_code=503)
        return await call_next(request)

    @app.get("/readyz")
    async def ready():
        with store.conn() as db:
            db.execute("SELECT delivery_id FROM events LIMIT 1").fetchone()
        return {
            "status": "ready",
            "build_sha": build_sha,
            "writes_enabled": writes_enabled,
            "agents_enabled": False,
            "repository": settings.github_repository,
            "protocol": "shared-claims:v1",
        }

    app.include_router(create_control_router(store, github, settings, build_sha))
    app.include_router(create_claim_router(store, github, settings))
    app.include_router(create_intake_router(store, github, settings))
    return app
