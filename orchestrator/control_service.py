"""Standalone queue/claim service. No agent, model or dispatch runtime is loaded."""
import asyncio
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .claim_api import create_claim_router
from .github_client import GitHubClient
from .issue_intake import create_intake_router
from .queue_discovery import discovery_loop
from .state_store import StateStore


def secret_file(path):
    """Read only the two explicit control-service secret files; never a shared env."""
    value = Path(path).read_text().strip()
    if len(value) < 32 or any(c.isspace() for c in value):
        raise ValueError('invalid control-service credential file')
    return value


def create_app(*, store=None, github=None, settings=None, writes_enabled=None, build_sha=None):
    if settings is None:
        repository = os.environ.get('CONTROL_REPOSITORY', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('CONTROL_REPOSITORY is required')
        settings = SimpleNamespace(github_repository=repository,
            orchestrator_token=secret_file('/run/secrets/control_token'))
        github = GitHubClient(secret_file('/run/secrets/control_github_token'))
        store = StateStore(os.environ.get('CONTROL_STATE_DB', '/state/control.db'))
    if writes_enabled is None:
        writes_enabled = os.environ.get('CONTROL_WRITES_ENABLED', 'false') == 'true'
    build_sha = build_sha or os.environ.get('CONTROL_BUILD_SHA', '')
    if not re.fullmatch(r'[0-9a-f]{40}', build_sha):
        raise ValueError('CONTROL_BUILD_SHA must identify the reviewed commit')

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()
        # Preflight mode starts no scanner, worker, remote mutation or API agent.
        task = asyncio.create_task(discovery_loop(stop, store, github, settings.github_repository, native_queue=False)) if writes_enabled else None
        try:
            yield
        finally:
            stop.set()
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def read_only_preflight(request: Request, call_next):
        if not writes_enabled and request.method not in {'GET', 'HEAD'}:
            return JSONResponse({'detail': 'CONTROL_WRITES_DISABLED'}, status_code=503)
        return await call_next(request)

    @app.get('/readyz')
    async def ready():
        # Static liveness/configuration only; does not assert GitHub reachability.
        with store.conn() as db:
            db.execute('SELECT delivery_id FROM events LIMIT 1').fetchone()
        return {'status': 'ready', 'build_sha': build_sha,
                'writes_enabled': writes_enabled, 'agents_enabled': False,
                'repository': settings.github_repository, 'protocol': 'shared-claims:v1'}

    app.include_router(create_claim_router(store, github, settings))
    app.include_router(create_intake_router(store, github, settings))
    return app
