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
from .handoff_gate import HandoffGateError, extract_handoff, validate_handoff
from .models import AgentRunResult, Handoff
from .readiness import all_ok, static_checks
from .security import verify_bearer, verify_github_signature
from .state_store import StateStore
from .task_router import build, next_labels
from .terminal_policy import resolve_terminal_policy

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
        else "workbuddy"
        if req.phase == "phase:deploy"
        else "human"
    )
    phase_name = (
        "prototype_validation"
        if req.phase == "phase:prototype"
        else "qa_acceptance"
        if req.phase == "phase:qa"
        else "deployment_plan"
        if req.phase == "phase:deploy"
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


def _trusted_comment(comment: dict, repository: str) -> bool:
    login = str((comment.get("user") or {}).get("login") or "")
    return login in {repository.split("/", 1)[0], "github-actions[bot]"}


def handoff_comment_exists(
    comments: list[dict],
    handoff: Handoff,
    repository: str,
) -> bool:
    expected = handoff.model_dump(mode="json")
    keys = (
        "task_id",
        "from_agent",
        "to_agent",
        "phase",
        "status",
        "source_sha",
        "blockers",
    )
    for comment in comments:
        if not _trusted_comment(comment, repository):
            continue
        try:
            payload = extract_handoff(str(comment.get("body") or ""))
        except HandoffGateError:
            continue
        if payload and all(payload.get(key) == expected.get(key) for key in keys):
            return True
    return False


def terminal_policy_comment_exists(
    comments: list[dict],
    repository: str,
    task_id: str,
    source_sha: str,
) -> bool:
    for comment in comments:
        if not _trusted_comment(comment, repository):
            continue
        body = str(comment.get("body") or "")
        if (
            "<!-- terminal-policy:v1 -->" in body
            and f"task_id={task_id}" in body.splitlines()
            and f"source_sha={source_sha}" in body.splitlines()
        ):
            return True
    return False


def dispatch_delivery_id(
    event_name: str | None,
    payload: dict,
    header_delivery_id: str | None,
) -> str:
    if event_name == "repository_dispatch":
        client_payload = payload.get("client_payload") or {}
        dispatch_key = str(client_payload.get("dispatch_key") or "")
        if dispatch_key:
            return f"repository-dispatch:{dispatch_key}"
    return header_delivery_id or str(uuid.uuid4())


def required_handoff(req):
    if req.phase == "phase:prototype":
        return {
            "from_agent": "codex",
            "to_agent": "workbuddy",
            "phase": "product_planning",
        }
    if req.phase == "phase:qa":
        return {
            "from_agent": "workreview",
            "to_agent": "workbuddy",
            "phase": "code_review",
        }
    if req.phase == "phase:deploy":
        return {
            "from_agent": "codex",
            "to_agent": "workbuddy",
            "phase": "release_review",
        }
    raise ValueError(f"unsupported WorkBuddy phase: {req.phase}")


async def require_current_head(req, expected_sha: str) -> None:
    """Fail closed unless the live PR head is the exact safe source revision."""
    identity = await github.get_pr_head_identity(
        req.repository,
        req.source_number,
    )
    if identity["head_repo_full_name"] != req.repository:
        raise RuntimeError(
            "UNSAFE_PR_HEAD_REPOSITORY: "
            f"expected={req.repository} live={identity['head_repo_full_name']}"
        )
    protected = {identity["base_ref"], identity["default_branch"]} - {""}
    if not identity["head_ref"] or identity["head_ref"] in protected:
        raise RuntimeError(
            f"UNSAFE_PR_HEAD_BRANCH: {identity['head_ref'] or '<empty>'}"
        )
    if identity["head_sha"] != expected_sha:
        raise RuntimeError(
            "CONCURRENT_BRANCH_ADVANCE: "
            f"expected={expected_sha} live={identity['head_sha']}"
        )


def workflow_label_set(labels: list[str]) -> set[str]:
    return {
        label
        for label in labels
        if label.startswith(("agent:", "phase:", "status:", "approval:"))
    }


def project_workflow_labels(
    live_labels: list[str],
    target_workflow: set[str],
) -> list[str]:
    unrelated = [
        label
        for label in live_labels
        if label not in workflow_label_set(live_labels)
    ]
    return sorted(set(unrelated) | target_workflow)


async def require_current_state(
    req,
    expected_sha: str,
    expected_workflow: set[str],
) -> list[str]:
    await require_current_head(req, expected_sha)
    labels = await github.get_issue_labels(req.repository, req.source_number)
    live_workflow = workflow_label_set(labels)
    if live_workflow != expected_workflow:
        raise RuntimeError(
            "WORKFLOW_STATE_SUPERSEDED: "
            f"expected={sorted(expected_workflow)} live={sorted(live_workflow)}"
        )
    return labels


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
    event_source_sha = req.source_sha

    if not github.configured:
        raise RuntimeError("GitHub write-back is required for handoff validation")

    # Webhook payloads are snapshots. Never claim or mutate stale ownership.
    todo_workflow = {"agent:workbuddy", req.phase, "status:todo"}
    running_workflow = {"agent:workbuddy", req.phase, "status:running"}
    checkpoint = event.get("checkpoint")
    if checkpoint:
        if checkpoint.get("source_sha") != req.source_sha:
            raise RuntimeError("CHECKPOINT_SOURCE_SHA_MISMATCH")
        current_labels = await github.get_issue_labels(
            req.repository,
            req.source_number,
        )
        allowed_workflows = [running_workflow]
        if checkpoint.get("transition_labels"):
            allowed_workflows.append(
                workflow_label_set(checkpoint["transition_labels"])
            )
        if workflow_label_set(current_labels) not in allowed_workflows:
            raise RuntimeError("CHECKPOINT_WORKFLOW_STATE_SUPERSEDED")
    else:
        current_labels = await require_current_state(
            req,
            req.source_sha,
            todo_workflow,
        )

    expected = required_handoff(req)
    comments = await github.list_comments(
        req.repository,
        req.source_number,
    )

    try:
        validate_handoff(
            comments,
            task_id=req.task_id,
            from_agent=expected["from_agent"],
            to_agent=expected["to_agent"],
            phase=expected["phase"],
            source_sha=req.source_sha,
            trusted_logins={
                req.repository.split("/", 1)[0],
                "github-actions[bot]",
            },
        )
    except HandoffGateError as exc:
        await require_current_state(req, req.source_sha, todo_workflow)
        await github.comment(
            req.repository,
            req.source_number,
            (
                "<!-- agent-handoff-gate:v1 -->\n"
                "### WorkBuddy start gate blocked\n\n"
                f"{exc}\n\n"
                "The WorkBuddy runner was **not started**. "
                "Fix the previous handoff and retry the same phase."
            ),
        )
        await require_current_state(req, req.source_sha, todo_workflow)
        await github.set_labels(
            req.repository,
            req.source_number,
            next_labels(
                req.agent,
                req.source_kind,
                current_labels,
                "blocked",
                [],
                phase=req.phase,
            ),
        )
        store.finish(event["delivery_id"], "done")
        return

    if github.configured and not checkpoint:
        latest_labels = await require_current_state(
            req,
            req.source_sha,
            todo_workflow,
        )
        running_labels = project_workflow_labels(
            latest_labels,
            running_workflow,
        )
        await github.set_labels(
            req.repository,
            req.source_number,
            running_labels,
        )
        await require_current_state(req, req.source_sha, running_workflow)

    if checkpoint:
        result = AgentRunResult.model_validate(checkpoint["result"])
    else:
        result = await workbuddy.run(req)
        if result.status == "success" and result.changes:
            store.checkpoint(
                event["delivery_id"],
                {
                    "source_sha": req.source_sha,
                    "result": result.model_dump(mode="json"),
                },
            )

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
            # A fresh run must still own the exact source revision. A resumed
            # run instead lets update_pr_files recognize only an exact direct-child
            # report commit whose file contents match the durable checkpoint.
            if not checkpoint:
                await require_current_state(req, req.source_sha, running_workflow)
            checkpoint_source_sha = req.source_sha
            new_sha = await github.update_pr_files(
                req.repository,
                req.source_number,
                result.changes,
                message_prefix="reports: WorkBuddy",
                expected_head_sha=req.source_sha,
            )
            result.artifacts = [
                change.path for change in result.changes
            ]
            # Every downstream handoff/dispatch must bind to the commit that
            # actually contains the WorkBuddy write-back, never the pre-write SHA.
            req.source_sha = new_sha
            if result.handoff:
                result.handoff.source_sha = new_sha
                result.handoff.artifacts = result.artifacts
            store.checkpoint(
                event["delivery_id"],
                {
                    "source_sha": checkpoint_source_sha,
                    "published_sha": new_sha,
                    "result": result.model_dump(mode="json"),
                },
            )

    handoff = ensure_handoff(req, result)
    transition_sha = handoff.source_sha or req.source_sha
    terminal_policy_text = (
        checkpoint.get("terminal_policy_text")
        if checkpoint
        else None
    )
    if (
        terminal_policy_text is None
        and result.status == "success"
        and req.phase == "phase:qa"
    ):
        issue_number = None
        if req.task_id.startswith("GH-ISSUE-"):
            try:
                issue_number = int(req.task_id.removeprefix("GH-ISSUE-"))
            except ValueError:
                issue_number = None
        if issue_number is not None:
            terminal_policy_text = await github.get_issue_body(
                req.repository, issue_number
            )

    await require_current_head(req, transition_sha)
    live_labels = await github.get_issue_labels(
        req.repository,
        req.source_number,
    )
    live_workflow = workflow_label_set(live_labels)
    transition_labels = (
        list(checkpoint["transition_labels"])
        if checkpoint and checkpoint.get("transition_labels")
        else next_labels(
            req.agent,
            req.source_kind,
            live_labels,
            result.status,
            result.next_labels,
            phase=req.phase,
            terminal_policy_text=terminal_policy_text,
        )
    )
    transition_workflow = workflow_label_set(transition_labels)
    transition_labels = project_workflow_labels(
        live_labels,
        transition_workflow,
    )
    if live_workflow not in (running_workflow, transition_workflow):
        raise RuntimeError(
            "WORKFLOW_STATE_SUPERSEDED: "
            f"live={sorted(live_workflow)} "
            f"allowed={[sorted(running_workflow), sorted(transition_workflow)]}"
        )

    checkpoint_payload = {
        "source_sha": event_source_sha,
        "published_sha": transition_sha,
        "result": result.model_dump(mode="json"),
        "transition_labels": transition_labels,
        "terminal_policy_text": terminal_policy_text,
    }
    store.checkpoint(event["delivery_id"], checkpoint_payload)

    comments = await github.list_comments(
        req.repository,
        req.source_number,
    )
    already_handed_off = handoff_comment_exists(
        comments,
        handoff,
        req.repository,
    )
    if live_workflow == transition_workflow and not already_handed_off:
        raise RuntimeError("TRANSITION_WITHOUT_EXACT_HANDOFF")

    if not already_handed_off:
        await require_current_state(req, transition_sha, running_workflow)
        await github.comment(
            req.repository,
            req.source_number,
            handoff_comment(handoff),
        )

    policy = None
    if result.status == "success" and req.phase == "phase:qa":
        policy = resolve_terminal_policy(terminal_policy_text or "")
        comments = await github.list_comments(
            req.repository,
            req.source_number,
        )
        already_recorded = terminal_policy_comment_exists(
            comments,
            req.repository,
            req.task_id,
            transition_sha,
        )
        if live_workflow == transition_workflow and not already_recorded:
            raise RuntimeError("TRANSITION_WITHOUT_TERMINAL_POLICY")
        if not already_recorded:
            await require_current_state(
                req,
                transition_sha,
                running_workflow,
            )
            await github.comment(
                req.repository,
                req.source_number,
                "<!-- terminal-policy:v1 -->\n"
                f"task_id={req.task_id}\n"
                f"source_sha={transition_sha}\n"
                f"policy={policy.policy or 'unresolved'}\n"
                f"release_enabled={str(policy.release_enabled).lower()}\n"
                f"reason={policy.reason}",
            )

    if live_workflow == running_workflow:
        latest_labels = await require_current_state(
            req,
            transition_sha,
            running_workflow,
        )
        transition_labels = project_workflow_labels(
            latest_labels,
            transition_workflow,
        )
        await github.set_labels(
            req.repository,
            req.source_number,
            transition_labels,
        )
        await require_current_state(
            req,
            transition_sha,
            transition_workflow,
        )

    if result.status == "success":
        if req.phase == "phase:prototype":
            event_type = "agent_chatgpt_implementation"
        elif req.phase == "phase:qa":
            if (
                "agent:codex" not in transition_labels
                or "phase:release" not in transition_labels
            ):
                store.finish(event["delivery_id"], "done")
                return
            event_type = "agent_codex_release"
        elif req.phase == "phase:deploy":
            event_type = "agent_execute_deployment"
        else:
            raise RuntimeError(
                f"no dispatch mapping for WorkBuddy phase {req.phase}"
            )

        await require_current_state(
            req,
            transition_sha,
            transition_workflow,
        )
        dispatch_key = (
            f"{event['delivery_id']}:{event_type}:{transition_sha}"
        )
        await github.repository_dispatch(
            req.repository,
            event_type,
            {
                "pr_number": req.source_number,
                "task_id": handoff.task_id,
                "head_ref": handoff.source_ref or req.source_ref,
                "source_sha": transition_sha,
                "dispatch_key": dispatch_key,
            },
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
    version="4.0.0",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "repository": settings.github_repository,
        "github_writeback_configured": github.configured,
        "handoff_protocol": "1.0",
        "agents": ["codex", "chatgpt", "openai-validator"],
    }


@app.get("/readyz")
async def readyz():
    checks = static_checks(settings)
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

    delivery_id = dispatch_delivery_id(
        x_github_event,
        payload,
        x_github_delivery,
    )
    return {
        "queued": store.enqueue(
            delivery_id,
            x_github_event or "unknown",
            payload,
        ),
        "delivery_id": delivery_id,
    }
