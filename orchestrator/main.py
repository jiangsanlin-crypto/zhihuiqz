import asyncio,json,uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI,Header,HTTPException,Request
from .adapters import HttpAgentAdapter
from .config import settings
from .github_client import GitHubClient
from .models import AgentRunResult
from .security import verify_bearer,verify_github_signature
from .state_store import StateStore
from .task_router import build,next_labels

store=StateStore(settings.state_db)
github=GitHubClient(settings.github_token)
adapters={
    "workbuddy":HttpAgentAdapter("workbuddy",settings.workbuddy_url,settings.workbuddy_token),
    "sandbox":HttpAgentAdapter("sandbox",settings.sandbox_url,settings.sandbox_token),
    "codex":HttpAgentAdapter("codex",settings.codex_url,settings.codex_token),
}

async def process(ev):
    routed=build(ev["event_name"],ev["payload"],settings.github_repository)
    if not routed:
        store.finish(ev["delivery_id"],"ignored")
        return

    req,current=routed
    if settings.github_token:
        await github.set_labels(
            req.repository,
            req.source_number,
            [x for x in current if not x.startswith("status:")]+["status:running"],
        )

    result=await adapters[req.agent].run(req)

    # A WorkBuddy issue run must hand off through a concrete PR. Never report
    # a successful handoff if no PR exists.
    if (
        req.agent=="workbuddy"
        and req.source_kind=="issue"
        and result.status=="success"
        and not result.pr_number
    ):
        result=AgentRunResult(
            status="blocked",
            summary="WorkBuddy returned success but did not provide a PR number.",
            artifacts=result.artifacts,
        )

    msg=(
        f"### Agent result: {req.agent}\n\n"
        f"- Task: {req.task_id}\n"
        f"- Status: **{result.status}**\n"
        f"- Summary: {result.summary}\n"
    )
    if result.artifacts:
        msg+="- Artifacts: "+", ".join(result.artifacts)+"\n"
    if result.pr_number:
        msg+=f"- PR: #{result.pr_number}\n"

    if settings.github_token:
        await github.comment(req.repository,req.source_number,msg)
        await github.set_labels(
            req.repository,
            req.source_number,
            next_labels(req.agent,req.source_kind,current,result.status,result.next_labels),
        )

        # Initial WorkBuddy spec PR enters the first sandbox gate.
        if (
            req.agent=="workbuddy"
            and req.source_kind=="issue"
            and result.status=="success"
            and result.pr_number
        ):
            await github.comment(
                req.repository,
                result.pr_number,
                f"Linked task #{req.source_number}. Starting sandbox QA gate.",
            )
            await github.set_labels(
                req.repository,
                result.pr_number,
                ["agent:sandbox","status:todo"],
            )

    if result.status=="failed":
        raise RuntimeError(result.summary)

    store.finish(ev["delivery_id"],"done")

async def worker(stop):
    while not stop.is_set():
        ev=store.claim_next()
        if not ev:
            await asyncio.sleep(2)
            continue
        try:
            await process(ev)
        except Exception as e:
            store.finish(
                ev["delivery_id"],
                "retry" if ev["attempts"]<settings.max_retries else "failed",
                str(e),
            )
            await asyncio.sleep(2)

@asynccontextmanager
async def lifespan(app):
    stop=asyncio.Event()
    task=asyncio.create_task(worker(stop))
    yield
    stop.set()
    await task

app=FastAPI(title="GitHub Multi-Agent Orchestrator",lifespan=lifespan)

@app.get("/healthz")
async def healthz():
    return {
        "ok":True,
        "repository":settings.github_repository,
        "github_writeback_configured":bool(settings.github_token),
    }

@app.post("/github/events",status_code=202)
async def events(
    request:Request,
    x_github_event:str|None=Header(None),
    x_github_delivery:str|None=Header(None),
    x_hub_signature_256:str|None=Header(None),
    authorization:str|None=Header(None),
):
    body=await request.body()
    trusted=(
        verify_bearer(settings.orchestrator_token,authorization)
        or verify_github_signature(settings.github_webhook_secret,body,x_hub_signature_256)
    )
    if not trusted:
        raise HTTPException(401,"invalid webhook authentication")
    try:
        payload=json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400,"invalid JSON")
    did=x_github_delivery or str(uuid.uuid4())
    return {
        "queued":store.enqueue(did,x_github_event or "unknown",payload),
        "delivery_id":did,
    }
