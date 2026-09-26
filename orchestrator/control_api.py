"""Authenticated wake-up of the shared controller and action dispatch."""
import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel, Field

from .security import verify_bearer
from .state_store import now
from .issue_intake import scan_issues
from .planning_recovery import recover_publications
from .timeout_monitor import monitor_timeouts
from .external_recovery import recover_external_once
from .blocker_recovery import recover_blockers_once
from .control_dispatch import ensure_dispatch_schema, dispatch_ready

STEPS = (
    scan_issues,
    recover_publications,
    monitor_timeouts,
    recover_external_once,
    recover_blockers_once,
)
class WakeRequest(BaseModel):
    model_config = {"extra": "forbid"}
    repository: str
    expected_build_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source: Literal["validator", "planner", "reconciler", "watchdog"]
    delivery_id: str = Field(pattern=r"^[A-Za-z0-9:._-]{1,150}$")


def create_control_router(store, github, settings, build_sha):
    with store.conn() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS control_requests(
            repository TEXT,delivery_id TEXT,source TEXT,status TEXT,expires_at TEXT,result_json TEXT,
            PRIMARY KEY(repository,delivery_id))"""
        )

    ensure_dispatch_schema(store)

    async def auth(authorization: str | None = Header(None)):
        if not verify_bearer(settings.orchestrator_token, authorization):
            raise HTTPException(401, "INVALID_AUTH")

    router = APIRouter(prefix="/control", dependencies=[Depends(auth)])

    @router.post("/wake")
    async def wake(value: WakeRequest):
        if (
            value.repository != settings.github_repository
            or value.expected_build_sha != build_sha
        ):
            raise HTTPException(409, "CONTROL_IDENTITY_CHANGED")
        with store.lock, store.conn() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT * FROM control_requests WHERE repository=? AND delivery_id=?",
                (value.repository, value.delivery_id),
            ).fetchone()
            if old and old["source"] != value.source:
                raise HTTPException(409, "DELIVERY_CHANGED")
            if old and old["status"] == "completed":
                return json.loads(old["result_json"])
            active = db.execute(
                "SELECT 1 FROM control_requests WHERE repository=? "
                "AND status='running' AND expires_at>?",
                (value.repository, now()),
            ).fetchone()
            if active:
                raise HTTPException(409, "CONTROL_TICK_ACTIVE")
            expiry = (
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat()
            db.execute(
                """INSERT INTO control_requests VALUES(?,?,?,?,?,NULL)
                ON CONFLICT(repository,delivery_id) DO UPDATE SET
                    status='running',expires_at=excluded.expires_at""",
                (
                    value.repository,
                    value.delivery_id,
                    value.source,
                    "running",
                    expiry,
                ),
            )

        counts = {}
        failed = []
        for step in STEPS:
            with store.conn() as db:
                lease = db.execute(
                    "SELECT status,expires_at FROM control_requests "
                    "WHERE repository=? AND delivery_id=?",
                    (value.repository, value.delivery_id),
                ).fetchone()
            if (
                not lease
                or lease["status"] != "running"
                or lease["expires_at"] != expiry
                or expiry <= now()
            ):
                raise HTTPException(409, "CONTROL_TICK_LEASE_LOST")
            try:
                counts[step.__name__] = await step(
                    store, github, value.repository
                )
            except Exception:
                failed.append(step.__name__)

        dispatch_count = 0
        if not failed:
            try:
                dispatch_count = await dispatch_ready(store, github, settings, build_sha)
            except Exception:
                failed.append("dispatch_ready")

        result = dict(
            status="completed" if not failed else "deferred",
            steps=counts,
            failed_steps=failed,
            execution_started=False,
            dispatch_performed=dispatch_count > 0,
            dispatch_count=dispatch_count,
        )
        with store.conn() as db:
            changed = db.execute(
                "UPDATE control_requests SET status=?,result_json=? "
                "WHERE repository=? AND delivery_id=? AND status='running' "
                "AND expires_at=? AND expires_at>?",
                (
                    "completed" if not failed else "retry",
                    json.dumps(result),
                    value.repository,
                    value.delivery_id,
                    expiry,
                    now(),
                ),
            ).rowcount
            if not changed:
                raise HTTPException(409, "CONTROL_TICK_LEASE_LOST")
        if failed:
            raise HTTPException(503, "CONTROL_EVIDENCE_INCOMPLETE")
        return result

    return router
