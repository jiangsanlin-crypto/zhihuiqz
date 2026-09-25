"""Authenticated shared leases. A lease is not a CI/review/production approval."""

import json
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .security import verify_bearer


class AcquireClaim(BaseModel):
    repository: str = Field(min_length=3, max_length=200)
    pr_number: int = Field(gt=0)
    source_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    head_ref: str = Field(min_length=1, max_length=250)
    task_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,150}$")
    phase: Literal["phase:implementation", "phase:code-review", "phase:escalation-repair", "phase:prototype", "phase:qa"]
    worker_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,150}$")
    request_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,150}$")


class OwnedClaim(BaseModel):
    delivery_id: str
    lease_id: str
    worker_id: str


def create_claim_router(store, github, settings):
    async def authenticated(authorization: str | None = Header(None)):
        if not verify_bearer(settings.orchestrator_token, authorization):
            raise HTTPException(401, "invalid claim authentication")

    router = APIRouter(prefix="/claims", dependencies=[Depends(authenticated)])

    def owned(value: OwnedClaim):
        row = store.get(value.delivery_id)
        if (not row or row["event_name"] != "external_claim"
            or row["lease_id"] != value.lease_id
            or json.loads(row["payload_json"]).get("worker_id") != value.worker_id):
            raise HTTPException(409, "WORKER_LEASE_LOST")
        binding = json.loads(row["payload_json"])
        try:
            store.assert_operation(binding["operation_key"], value.delivery_id, value.lease_id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return row, binding

    async def current(binding, *, resumed=False):
        if not settings.github_repository or binding["repository"] != settings.github_repository:
            raise HTTPException(409, "REPOSITORY_MISMATCH")
        pr = await github.get_pr_snapshot(binding["repository"], binding["pr_number"])
        head, base = pr.get("head") or {}, pr.get("base") or {}
        if (pr.get("state") != "open" or pr.get("merged_at")
            or (head.get("repo") or {}).get("full_name") != binding["repository"]
            or head.get("ref") != binding["head_ref"]
            or head.get("ref") in {"main", base.get("ref"), (head.get("repo") or {}).get("default_branch")}):
            raise HTTPException(409, "PR_BRANCH_IDENTITY_CHANGED")
        if head.get("sha") != binding["source_sha"]:
            raise HTTPException(409, "HEAD_CHANGED")
        if f"<!-- agent-task-id:{binding['task_id']} -->" not in str(pr.get("body") or ""):
            raise HTTPException(409, "TASK_CHANGED")
        labels = {item["name"] if isinstance(item, dict) else item for item in pr.get("labels", [])}
        route = {x for x in labels if x.startswith(("agent:", "phase:", "status:", "approval:"))}
        expected = {binding["agent"], binding["phase"], "status:todo"}
        running = {binding["agent"], binding["phase"], "status:running"}
        if (route != expected and not (resumed and route == running)) or any(
            x.startswith(("blocker:", "recovery:", "watchdog:")) for x in labels
        ):
            raise HTTPException(409, "STATE_CHANGED")

    def response(row):
        return {key: row[key] for key in ("delivery_id", "lease_id", "lease_expires_at")}

    @router.post("/acquire")
    async def acquire(value: AcquireClaim):
        binding = value.model_dump(exclude={"worker_id", "request_id"})
        binding["agent"] = ("agent:chatgpt" if value.phase == "phase:implementation"
                            else "agent:workreview" if value.phase in {"phase:code-review", "phase:escalation-repair"}
                            else "agent:workbuddy")
        binding["operation_key"] = json.dumps(
            [value.repository, value.pr_number, value.source_sha, value.phase], separators=(",", ":"))
        previous = store.get(store.external_delivery_id(value.worker_id, value.request_id))
        if previous:
            owned(OwnedClaim(delivery_id=previous["delivery_id"],
                             lease_id=previous["lease_id"] or "", worker_id=value.worker_id))
        await current(binding, resumed=previous is not None)
        try:
            row = store.claim_external(binding, value.worker_id, value.request_id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        try:
            # A push or human-wait transition during acquisition revokes it.
            await current(binding, resumed=previous is not None)
        except HTTPException:
            store.finish(row["delivery_id"], "superseded", lease_id=row["lease_id"])
            raise
        return response(row)

    @router.post("/heartbeat")
    async def heartbeat(value: OwnedClaim):
        row, binding = owned(value)
        try:
            await current(binding, resumed=True)
        except HTTPException:
            store.finish(row["delivery_id"], "superseded", lease_id=row["lease_id"])
            raise
        if not store.heartbeat(value.delivery_id, value.lease_id):
            raise HTTPException(409, "WORKER_LEASE_LOST")
        return response(store.get(value.delivery_id))

    @router.post("/release")
    async def release(value: OwnedClaim):
        owned(value)
        if not store.finish(value.delivery_id, "done", lease_id=value.lease_id):
            raise HTTPException(409, "WORKER_LEASE_LOST")
        return {"released": True}

    return router
