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
from .queue_discovery import discover

STEPS = (
    scan_issues,
    recover_publications,
    monitor_timeouts,
    recover_external_once,
    recover_blockers_once,
)
DISPATCH_COOLDOWN_SECONDS = 10 * 60


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
        db.execute(
            """CREATE TABLE IF NOT EXISTS control_dispatches(
            repository TEXT,dispatch_key TEXT,event_type TEXT,last_dispatched_at TEXT,
            attempt INTEGER DEFAULT 0,status TEXT,payload_json TEXT,
            PRIMARY KEY(repository,dispatch_key))"""
        )

    async def auth(authorization: str | None = Header(None)):
        if not verify_bearer(settings.orchestrator_token, authorization):
            raise HTTPException(401, "INVALID_AUTH")

    router = APIRouter(prefix="/control", dependencies=[Depends(auth)])

    def dispatch_due(key: str) -> bool:
        with store.conn() as db:
            row = db.execute(
                "SELECT last_dispatched_at,status FROM control_dispatches "
                "WHERE repository=? AND dispatch_key=?",
                (settings.github_repository, key),
            ).fetchone()
        if not row or not row["last_dispatched_at"]:
            return True
        try:
            last = datetime.fromisoformat(row["last_dispatched_at"])
        except ValueError:
            return True
        return (
            datetime.now(timezone.utc) - last
        ).total_seconds() >= DISPATCH_COOLDOWN_SECONDS

    def record_dispatch(key: str, event_type: str, payload: dict, status: str) -> None:
        with store.conn() as db:
            db.execute(
                """INSERT INTO control_dispatches(
                    repository,dispatch_key,event_type,last_dispatched_at,attempt,status,payload_json
                ) VALUES(?,?,?,?,1,?,?)
                ON CONFLICT(repository,dispatch_key) DO UPDATE SET
                    event_type=excluded.event_type,
                    last_dispatched_at=excluded.last_dispatched_at,
                    attempt=control_dispatches.attempt+1,
                    status=excluded.status,
                    payload_json=excluded.payload_json""",
                (
                    settings.github_repository,
                    key,
                    event_type,
                    now(),
                    status,
                    json.dumps(payload, sort_keys=True),
                ),
            )

    async def dispatch_ready() -> int:
        repo = settings.github_repository
        count = 0
        # Unit/preflight callers may intentionally provide a read-only GitHub
        # stub. Production GitHubClient always exposes repository_dispatch.
        if not hasattr(github, "repository_dispatch"):
            return 0

        with store.conn() as db:
            publications = {
                row["issue_number"]: dict(row)
                for row in db.execute(
                    "SELECT * FROM planning_publications WHERE repository=? AND status='prepared'",
                    (repo,),
                ).fetchall()
            }

        for row in store.intake_items(repo):
            issue_number = int(row["issue_number"])
            publication = publications.get(issue_number)
            if publication:
                lease_live = (
                    row["status"] == "leased"
                    and row["expires_at"]
                    and row["expires_at"] > now()
                )
                if lease_live:
                    continue
                key = f"planner-resume:{issue_number}:{publication['publication_id']}"
                if not dispatch_due(key):
                    continue
                payload = {
                    "issue_number": issue_number,
                    "generation": row["generation"],
                    "publication_id": publication["publication_id"],
                    "control_build_sha": build_sha,
                    "dispatch_key": key,
                }
                event_type = "shared_codex_resume"
                try:
                    await github.repository_dispatch(repo, event_type, payload)
                except Exception:
                    record_dispatch(key, event_type, payload, "failed")
                    raise
                record_dispatch(key, event_type, payload, "sent")
                count += 1
                continue

            claimable = row["status"] == "awaiting_planner" or (
                row["status"] == "leased"
                and row["expires_at"]
                and row["expires_at"] <= now()
            )
            if not claimable:
                continue
            key = f"planner:{issue_number}:{row['generation']}"
            if not dispatch_due(key):
                continue
            payload = {
                "issue_number": issue_number,
                "generation": row["generation"],
                "control_build_sha": build_sha,
                "dispatch_key": key,
            }
            event_type = "shared_codex_product"
            try:
                await github.repository_dispatch(repo, event_type, payload)
            except Exception:
                record_dispatch(key, event_type, payload, "failed")
                raise
            record_dispatch(key, event_type, payload, "sent")
            count += 1

        for _pr, binding in await discover(github, repo):
            if binding["phase"] not in {"phase:prototype", "phase:qa"}:
                continue
            operation_key = json.dumps(
                [
                    repo,
                    binding["pr_number"],
                    binding["source_sha"],
                    binding["phase"],
                ],
                separators=(",", ":"),
            )
            if store.operation_active(operation_key):
                continue
            key = (
                f"validator:{binding['pr_number']}:{binding['source_sha']}:"
                f"{binding['phase']}"
            )
            if not dispatch_due(key):
                continue
            event_type = (
                "shared_validator_prototype"
                if binding["phase"] == "phase:prototype"
                else "shared_validator_qa"
            )
            payload = {
                **binding,
                "control_build_sha": build_sha,
                "dispatch_key": key,
            }
            try:
                await github.repository_dispatch(repo, event_type, payload)
            except Exception:
                record_dispatch(key, event_type, payload, "failed")
                raise
            record_dispatch(key, event_type, payload, "sent")
            count += 1
        return count

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
                dispatch_count = await dispatch_ready()
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
