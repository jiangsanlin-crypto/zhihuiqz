"""Idempotent dispatch from durable shared state to model execution surfaces."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .queue_discovery import discover
from .state_store import now

DISPATCH_COOLDOWN_SECONDS = 10 * 60


def ensure_dispatch_schema(store) -> None:
    with store.conn() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS control_dispatches(
            repository TEXT,dispatch_key TEXT,event_type TEXT,last_dispatched_at TEXT,
            attempt INTEGER DEFAULT 0,status TEXT,payload_json TEXT,
            PRIMARY KEY(repository,dispatch_key))"""
        )


def _dispatch_due(store, repository: str, key: str) -> bool:
    with store.conn() as db:
        row = db.execute(
            "SELECT last_dispatched_at,status FROM control_dispatches "
            "WHERE repository=? AND dispatch_key=?",
            (repository, key),
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


def _record_dispatch(store, repository: str, key: str, event_type: str,
                     payload: dict, status: str) -> None:
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
                repository,
                key,
                event_type,
                now(),
                status,
                json.dumps(payload, sort_keys=True),
            ),
        )


async def dispatch_ready(store, github, settings, build_sha: str) -> int:
    """Dispatch only phases that execute in GitHub Actions.

    Account-backed implementation and independent Review consumers observe the
    same projected queue but are not model-dispatched from this service.
    """
    repo = settings.github_repository
    count = 0
    if not hasattr(github, "repository_dispatch"):
        return 0
    ensure_dispatch_schema(store)

    with store.conn() as db:
        publications = {
            row["issue_number"]: dict(row)
            for row in db.execute(
                "SELECT * FROM planning_publications "
                "WHERE repository=? AND status='prepared'",
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
            if not _dispatch_due(store, repo, key):
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
                _record_dispatch(store, repo, key, event_type, payload, "failed")
                raise
            _record_dispatch(store, repo, key, event_type, payload, "sent")
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
        if not _dispatch_due(store, repo, key):
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
            _record_dispatch(store, repo, key, event_type, payload, "failed")
            raise
        _record_dispatch(store, repo, key, event_type, payload, "sent")
        count += 1

    for _pr, binding in await discover(github, repo):
        if binding["phase"] not in {"phase:prototype", "phase:qa"}:
            continue
        operation_key = json.dumps(
            [repo, binding["pr_number"], binding["source_sha"], binding["phase"]],
            separators=(",", ":"),
        )
        if store.operation_active(operation_key):
            continue
        key = (
            f"validator:{binding['pr_number']}:{binding['source_sha']}:"
            f"{binding['phase']}"
        )
        if not _dispatch_due(store, repo, key):
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
            _record_dispatch(store, repo, key, event_type, payload, "failed")
            raise
        _record_dispatch(store, repo, key, event_type, payload, "sent")
        count += 1
    return count
