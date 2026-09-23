from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .adapters import HttpAgentAdapter
from .config import settings
from .github_client import GitHubClient
from .models import AgentRunResult, Handoff
from .readiness import all_ok, static_checks
from .security import verify_bearer, verify_github_signature
from .state_store import StateStore
from .task_router import build, next_labels

store = StateStore(settings.state_db)
github = GitHubClient(settings.github_token)
workbuddy = HttpAgentAdapter(
    "workbuddy",
    settings.workbuddy_url,
    settings.workbuddy_token,
)


def ensure_handoff(req, result: AgentRunResult) -> Handoff:
    if result.handoff:
        handoff = result.handoff.model_copy(deep=True)
        handoff.pr_number = handoff.pr_number or req.source_number
        handoff.source_ref = handoff.source_ref or req.source_ref
        handoff.source_sha = handoff.source_sha or req.source_sha
        return handoff

    next_agent = (
        "chatgpt"
        if req.phase == "phase:prototype"
        else "codex"
        if req.phase == "phase:qa"
        else "human"
    )
    phase_name = (
        "prototype_validation"
        if req.phase == "phase:prototype"
        else "qa_acceptance"
        if req.phase == "phase:qa"
        else "workbuddy"
    )

    return Handoff(
        task_id=req.task_id,
        from_agent="workbuddy",
        to_agent=next_agent if result.status == "success" else "human",
        phase=phase_name,
        status=result.status,
        summary=result.summary,
        model=settings.workbuddy_model,
        effort="workbuddy-configured",
        artifacts=result.artifacts,
        checks=result.checks,
        blockers=[] if result.status == "success" else [result.summary],
        source_ref=req.source_ref,
        source_sha=req.source_sha,
        pr_number=req.source_number,
    )


def handoff_comment(handoff: Handoff) -> str:
    data = handoff.model_dump()
    for check in data.get("checks", []):
        check["detail"] = str(check.get("detail") or "")[-2000:]

    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return (
        "<!-- agent-handoff:v1 -->\n"
        f"### Agent handoff: {handoff.from_agent} → "
        f"{handoff.to_agent or 'none'}\n\n"
        f"**Task:** `{handoff.task_id}`  \n"
        f"**Phase:** `{handoff.phase}`  \n"
        f"**Model:** `{handoff.model or 'n/a'}`  \n"
        f"**Status:** **{handoff.status}**\n\n"
        f"{handoff.summary}\n\n"
        "```json\n"
        f"{payload}\n"
        "```"
    )


async def process(event: dict) -> None:
    routed = build(
        event["event_name"],
        event["payload"],
        settings.github_repository,
    )
    if not routed:
        store.finish(event["delivery_id"], "ignored")
        return

    req, current_labels = routed

    if github.configured:
        running_labels = [
            label
            for label in current_labels
            if not label.startswith("status:")
        ]
        running_labels.append("status:running")
        await github.set_labels(
            req.repository,
            req.source_number,
            sorted(set(running_labels)),
        )

    result = await workbuddy.run(req)

    if result.status == "success" and result.changes:
        if not github.configured:
            result = AgentRunResult(
                status="blocked",
                summary="WorkBuddy produced reports but GitHub write-back is unavailable.",
                artifacts=result.artifacts,
                changes=result.changes,
                checks=result.checks,
            )
        else:
            new_sha = await github.update_pr_files(
                req.repository,
                req.source_number,
                result.changes,
                message_prefix="reports: WorkBuddy",
            )
            result.artifacts = [
                change.path for change in result.changes
            ]
            if result.handoff:
                result.handoff.source_sha = new_sha
                result.handoff.artifacts = result.artifacts

    handoff = ensure_handoff(req, result)
    message = handoff_comment(handoff)

    if github.configured:
        await github.comment(
            req.repository,
            req.source_number,
            message,
        )
        await github.set_labels(
            req.repository,
            req.source_number,
            next_labels(
                req.agent,
                req.source_kind,
                current_labels,
                result.status,
                result.next_labels,
                phase=req.phase,
            ),
        )

    if result.status == "failed":
        raise RuntimeError(result.summary)

    store.finish(event["delivery_id"], "done")


async def worker(stop: asyncio.Event) -> None:
    while not stop.is_set():
        event = store.claim_next()
        if not event:
            await asyncio.sleep(2)
            continue

        try:
            await process(event)
        except Exception as exc:
            store.finish(
                event["delivery_id"],
                (
                    "retry"
                    if event["attempts"] < settings.max_retries
                    else "failed"
                ),
                str(exc),
            )
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = asyncio.create_task(worker(stop))
    yield
    stop.set()
    await task


app = FastAPI(
    title="GitHub Multi-Agent Orchestrator",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "repository": settings.github_repository,
        "github_writeback_configured": github.configured,
        "handoff_protocol": "1.0",
        "agents": ["codex", "chatgpt", "workbuddy"],
    }


@app.get("/readyz")
async def readyz():
    checks = static_checks(settings)
    workbuddy_health = await workbuddy.health()

    checks["workbuddy_live"] = {
        "ok": (
            bool(workbuddy_health.get("ok"))
            and bool(workbuddy_health.get("oauth_configured"))
            and bool(workbuddy_health.get("model_lock_confirmed"))
            and workbuddy_health.get("expected_model") == "GLM-5.3-Flash"
        ),
        "detail": {
            key: value
            for key, value in workbuddy_health.items()
            if key not in {"token", "access_token", "refresh_token"}
        },
    }

    ready = all_ok(checks)
    payload = {
        "ok": ready,
        "handoff_protocol": "1.0",
        "checks": checks,
    }
    if ready:
        return payload
    return JSONResponse(status_code=503, content=payload)


@app.post("/github/events", status_code=202)
async def events(
    request: Request,
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
    authorization: str | None = Header(None),
):
    body = await request.body()
    trusted = (
        verify_bearer(settings.orchestrator_token, authorization)
        or verify_github_signature(
            settings.github_webhook_secret,
            body,
            x_hub_signature_256,
        )
    )
    if not trusted:
        raise HTTPException(401, "invalid webhook authentication")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "invalid JSON")

    delivery_id = x_github_delivery or str(uuid.uuid4())
    return {
        "queued": store.enqueue(
            delivery_id,
            x_github_event or "unknown",
            payload,
        ),
        "delivery_id": delivery_id,
    }
