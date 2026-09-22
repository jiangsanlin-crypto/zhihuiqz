from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from .adapters import HttpAgentAdapter
from .config import settings
from .github_client import GitHubClient
from .models import AgentRunResult, Handoff
from .security import verify_bearer, verify_github_signature
from .state_store import StateStore
from .task_router import build, next_labels

store = StateStore(settings.state_db)
github = GitHubClient(settings.github_token)
adapters = {
    "workbuddy": HttpAgentAdapter("workbuddy", settings.workbuddy_url, settings.workbuddy_token),
    "sandbox": HttpAgentAdapter("sandbox", settings.sandbox_url, settings.sandbox_token),
    "codex": HttpAgentAdapter("codex", settings.codex_url, settings.codex_token),
}


def default_target(req, status: str):
    if status != "success":
        return "human"
    if req.agent == "workbuddy":
        return "sandbox" if req.source_kind == "issue" else "human"
    if req.agent == "sandbox":
        labels = {
            item.get("name")
            for item in ((req.payload.get("pull_request") or {}).get("labels") or [])
            if isinstance(item, dict)
        }
        return "workbuddy" if "needs:qa" in labels else "codex"
    if req.agent == "codex":
        return "sandbox"
    return "human"


def phase_for(req) -> str:
    if req.agent == "workbuddy":
        return "specification" if req.source_kind == "issue" else "product_review"
    if req.agent == "sandbox":
        labels = {
            item.get("name")
            for item in ((req.payload.get("pull_request") or {}).get("labels") or [])
            if isinstance(item, dict)
        }
        return "final_qa" if "needs:qa" in labels else "spec_qa"
    return "implementation"


def ensure_handoff(req, result: AgentRunResult) -> Handoff:
    if result.handoff:
        handoff = result.handoff.model_copy(deep=True)
        handoff.pr_number = handoff.pr_number or result.pr_number
        handoff.source_ref = handoff.source_ref or req.source_ref
        handoff.source_sha = handoff.source_sha or req.source_sha
        return handoff
    return Handoff(
        task_id=req.task_id,
        from_agent=req.agent,
        to_agent=default_target(req, result.status),
        phase=phase_for(req),
        status=result.status,
        summary=result.summary,
        artifacts=result.artifacts,
        checks=result.checks,
        blockers=[] if result.status == "success" else [result.summary],
        source_ref=req.source_ref,
        source_sha=req.source_sha,
        pr_number=result.pr_number,
    )


def handoff_comment(handoff: Handoff) -> str:
    data = handoff.model_dump()
    for check in data.get("checks", []):
        check["detail"] = str(check.get("detail") or "")[-2000:]
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return (
        "<!-- agent-handoff:v1 -->\n"
        f"### Agent handoff: {handoff.from_agent} → {handoff.to_agent or 'none'}\n\n"
        f"**Task:** \`{handoff.task_id}\`  \n"
        f"**Phase:** \`{handoff.phase}\`  \n"
        f"**Status:** **{handoff.status}**\n\n"
        f"{handoff.summary}\n\n"
        "\`\`\`json\n"
        f"{payload}\n"
        "\`\`\`"
    )


async def process(event: dict) -> None:
    routed = build(event["event_name"], event["payload"], settings.github_repository)
    if not routed:
        store.finish(event["delivery_id"], "ignored")
        return

    req, current_labels = routed

    if settings.github_token:
        running_labels = [
            label for label in current_labels if not label.startswith("status:")
        ]
        running_labels.append("status:running")
        await github.set_labels(
            req.repository,
            req.source_number,
            sorted(set(running_labels)),
        )

    result = await adapters[req.agent].run(req)

    if (
        req.agent == "workbuddy"
        and req.source_kind == "issue"
        and result.status == "success"
    ):
        if not result.changes:
            result = AgentRunResult(
                status="blocked",
                summary="WorkBuddy returned success but no specification file changes were provided.",
                artifacts=result.artifacts,
                checks=result.checks,
            )
        elif not github.configured:
            result = AgentRunResult(
                status="blocked",
                summary="The orchestrator cannot create the specification PR because GitHub write-back is not configured.",
                artifacts=result.artifacts,
                checks=result.checks,
                changes=result.changes,
            )
        else:
            issue = req.payload.get("issue") or {}
            pr_number = await github.create_or_update_spec_pr(
                req.repository,
                req.source_number,
                req.task_id,
                str(issue.get("title") or req.task_id),
                result.changes,
            )
            result.pr_number = pr_number
            if result.handoff:
                result.handoff.pr_number = pr_number

    handoff = ensure_handoff(req, result)
    message = handoff_comment(handoff)

    if settings.github_token:
        await github.comment(req.repository, req.source_number, message)
        await github.set_labels(
            req.repository,
            req.source_number,
            next_labels(
                req.agent,
                req.source_kind,
                current_labels,
                result.status,
                result.next_labels,
            ),
        )

        if (
            req.agent == "workbuddy"
            and req.source_kind == "issue"
            and result.status == "success"
            and result.pr_number
        ):
            await github.comment(
                req.repository,
                result.pr_number,
                f"Linked source issue: #{req.source_number}\n\n" + handoff_comment(handoff),
            )
            await github.set_labels(
                req.repository,
                result.pr_number,
                ["agent:sandbox", "status:todo"],
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
                "retry" if event["attempts"] < settings.max_retries else "failed",
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
    version="1.1.0",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "repository": settings.github_repository,
        "github_writeback_configured": github.configured,
        "handoff_protocol": "1.0",
    }


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
        "queued": store.enqueue(delivery_id, x_github_event or "unknown", payload),
        "delivery_id": delivery_id,
    }
