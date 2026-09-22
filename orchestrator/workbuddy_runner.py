from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException

from .models import AgentRunRequest, AgentRunResult, FileChange, Handoff
from .security import verify_bearer

RUNNER_TOKEN = os.getenv("WORKBUDDY_RUNNER_TOKEN", "")
ALLOWED_REPO = os.getenv("WORKBUDDY_ALLOWED_REPO", "")
WB_BASE = os.getenv(
    "WORKBUDDY_API_BASE",
    "https://www.workbuddy.cn/openapi/v2",
).rstrip("/")
WB_ACCESS_TOKEN = os.getenv("WORKBUDDY_ACCESS_TOKEN", "")
WB_REFRESH_TOKEN = os.getenv("WORKBUDDY_REFRESH_TOKEN", "")
WB_CLIENT_ID = os.getenv("WORKBUDDY_CLIENT_ID", "")
WB_CLIENT_SECRET = os.getenv("WORKBUDDY_CLIENT_SECRET", "")
WB_TOKEN_FILE = Path(
    os.getenv("WORKBUDDY_TOKEN_FILE", "/app/data/workbuddy_oauth.json")
)
WB_TIMEOUT = int(os.getenv("WORKBUDDY_TIMEOUT_SECONDS", "900"))
WB_POLL = max(2, int(os.getenv("WORKBUDDY_POLL_SECONDS", "5")))

ALLOWED_SPEC_FILES = {
    "docs/PRD.md",
    "docs/MATCHING_SPEC.md",
    "docs/I18N.md",
    "docs/MONETIZATION.md",
    "TASKS.md",
}
MAX_FILE_BYTES = 100_000

app = FastAPI(title="WorkBuddy Runner")


def unwrap(payload: Any) -> Any:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        if "access_token" in payload["data"] or "task_id" in payload["data"]:
            return payload["data"]
    return payload


def parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("WorkBuddy did not return a JSON object")
    obj = json.loads(raw[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("WorkBuddy result must be a JSON object")
    return obj


class WorkBuddyClient:
    def __init__(self):
        self.access_token = WB_ACCESS_TOKEN
        self.refresh_token = WB_REFRESH_TOKEN
        self.expires_at = 0.0
        self._load_token_file()

    def _load_token_file(self) -> None:
        try:
            if WB_TOKEN_FILE.exists():
                data = json.loads(WB_TOKEN_FILE.read_text())
                self.access_token = data.get("access_token") or self.access_token
                self.refresh_token = data.get("refresh_token") or self.refresh_token
                self.expires_at = float(data.get("expires_at") or 0)
        except Exception:
            pass

    def _save_token_file(self, payload: dict[str, Any]) -> None:
        WB_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = WB_TOKEN_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        os.chmod(tmp, 0o600)
        tmp.replace(WB_TOKEN_FILE)

    async def refresh(self) -> str:
        if not (self.refresh_token and WB_CLIENT_ID and WB_CLIENT_SECRET):
            if self.access_token:
                return self.access_token
            raise RuntimeError(
                "WorkBuddy OAuth is not configured. Set an access token or "
                "client_id/client_secret/refresh_token."
            )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{WB_BASE}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": WB_CLIENT_ID,
                    "client_secret": WB_CLIENT_SECRET,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = unwrap(response.json())
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token") or self.refresh_token
        self.expires_at = time.time() + int(data.get("expires_in") or 3600) - 60
        self._save_token_file(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at,
            }
        )
        return self.access_token

    async def token(self) -> str:
        if self.access_token and (
            self.expires_at == 0 or self.expires_at > time.time() + 60
        ):
            return self.access_token
        return await self.refresh()

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        token = await self.token()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Accept", "application/json")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs,
            )
        if response.status_code == 401 and self.refresh_token:
            token = await self.refresh()
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs,
                )
        response.raise_for_status()
        return response

    async def run_cloud_task(self, prompt: str, name: str) -> str:
        response = await self.request(
            "POST",
            f"{WB_BASE}/tasks",
            json={"prompt": prompt, "name": name[:120]},
            headers={"Content-Type": "application/json"},
        )
        task = unwrap(response.json())
        task_id = str(task["task_id"])
        deadline = time.monotonic() + WB_TIMEOUT
        last = task

        import asyncio

        while time.monotonic() < deadline:
            status = str(last.get("status") or "").lower()
            if status == "completed":
                break
            if status in {"failed", "archived", "deleted"}:
                raise RuntimeError(
                    f"WorkBuddy task ended with status={status}"
                )
            await asyncio.sleep(WB_POLL)
            query = await self.request("GET", f"{WB_BASE}/tasks/{task_id}")
            last = unwrap(query.json())
        else:
            raise RuntimeError("WorkBuddy cloud task timed out")

        link = last.get("link") or task.get("link")
        ticket = last.get("token") or task.get("token")
        if not link or not ticket:
            query = await self.request("GET", f"{WB_BASE}/tasks/{task_id}")
            last = unwrap(query.json())
            link = last.get("link")
            ticket = last.get("token")
        if not link or not ticket:
            raise RuntimeError(
                "WorkBuddy completed but did not return ACP link/token"
            )

        sandbox_url = str(link)
        if sandbox_url.endswith("/acp"):
            sandbox_url = sandbox_url[:-4]

        async with httpx.AsyncClient(timeout=60) as client:
            artifacts_response = await client.get(
                f"{sandbox_url}/api/session/artifacts",
                params={
                    "sessionId": task_id,
                    "type": "overview",
                    "limit": 50,
                    "offset": 0,
                },
                headers={
                    "Authorization": f"Bearer {ticket}",
                    "Accept": "application/json",
                },
            )
            artifacts_response.raise_for_status()
            body = artifacts_response.json()

        data = body.get("data") if isinstance(body, dict) else None
        entries = (data or {}).get("artifacts") or []
        candidates = []
        for entry in entries:
            artifact = (entry or {}).get("artifact") or {}
            if artifact.get("type") == "overview" and artifact.get("text"):
                candidates.append(
                    (artifact.get("updatedAt") or 0, artifact["text"])
                )
        if not candidates:
            raise RuntimeError(
                "WorkBuddy task produced no overview artifact"
            )
        candidates.sort(key=lambda item: item[0])
        return str(candidates[-1][1])


def validate_spec_result(obj: dict[str, Any]) -> tuple[str, list[FileChange]]:
    if str(obj.get("status") or "").lower() != "success":
        raise ValueError(
            obj.get("summary")
            or "WorkBuddy did not approve the specification"
        )

    raw = obj.get("files")
    if not isinstance(raw, list):
        raise ValueError("WorkBuddy JSON has no files array")

    changes: list[FileChange] = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid files item")
        path = str(item.get("path") or "")
        content = item.get("content")
        if path not in ALLOWED_SPEC_FILES:
            raise ValueError(f"Path not allowed: {path}")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"Empty content for {path}")
        if len(content.encode()) > MAX_FILE_BYTES:
            raise ValueError(f"File too large: {path}")
        changes.append(
            FileChange(
                path=path,
                content=content,
                purpose=str(item.get("purpose") or ""),
            )
        )
        seen.add(path)

    missing = ALLOWED_SPEC_FILES - seen
    if missing:
        raise ValueError(
            "Missing required files: " + ", ".join(sorted(missing))
        )
    return str(
        obj.get("summary") or "WorkBuddy specification completed"
    ), changes


def specification_prompt(req: AgentRunRequest) -> str:
    issue = req.payload.get("issue") or {}
    title = str(issue.get("title") or req.task_id)
    body = str(issue.get("body") or "")
    repo_url = f"https://github.com/{req.repository}"

    return f"""You are WorkBuddy, the product/business specification agent.

Task ID: {req.task_id}
Public repository: {repo_url}
Issue: {title}

Issue body:
{body}

The repository is public. Read it directly without asking for GitHub OAuth,
GitHub tokens, or connector authorization. Inspect README, AGENTS.md, TASKS.md
and relevant public files before producing the specification.

Produce the handoff for a multilingual Cambodia recruitment product.

Hard constraints:
- Default language is Khmer, then English, then Chinese.
- Paid employer features may improve discovery/filtering/reach, but payment
  must never directly increase relevance score.
- Use synthetic examples only; never invent real candidate personal data.
- Do not propose automatic production deployment or automatic merge to main.
- Do not request or expose secrets.

Return JSON ONLY:
{{
  "status": "success",
  "summary": "short summary",
  "files": [
    {{"path":"docs/PRD.md","content":"full markdown","purpose":"product requirements"}},
    {{"path":"docs/MATCHING_SPEC.md","content":"full markdown","purpose":"matching specification"}},
    {{"path":"docs/I18N.md","content":"full markdown","purpose":"language specification"}},
    {{"path":"docs/MONETIZATION.md","content":"full markdown","purpose":"monetization boundaries"}},
    {{"path":"TASKS.md","content":"full markdown","purpose":"engineering tasks"}}
  ]
}}

Do not include code fences or commentary outside the JSON.
"""


def final_review_prompt(req: AgentRunRequest) -> str:
    pr_url = f"https://github.com/{req.repository}/pull/{req.source_number}"
    repo_url = f"https://github.com/{req.repository}"
    return f"""You are WorkBuddy performing the final product/business review.

Task ID: {req.task_id}
Public repository: {repo_url}
Pull request: {pr_url}

Both are public. Read them directly without asking for GitHub authorization.
Read the PR diff, PR discussion/handoff comments, specification documents and
current implementation.

Check:
- the implementation matches the approved product requirements;
- Khmer is default, English second, Chinese third;
- employer payment never directly changes relevance score;
- no production credentials or real candidate data were introduced;
- no automatic production deployment or main auto-merge was introduced;
- earlier Sandbox and Codex handoffs have been addressed.

Return JSON ONLY:
{{"status":"success","summary":"review passed: ..."}}
or
{{"status":"blocked","summary":"specific product/business blockers: ..."}}

Do not include code fences.
"""


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "agent": "workbuddy",
        "allowed_repo": ALLOWED_REPO,
        "github_auth_required_for_read": False,
        "oauth_configured": bool(
            WB_ACCESS_TOKEN
            or (
                WB_REFRESH_TOKEN
                and WB_CLIENT_ID
                and WB_CLIENT_SECRET
            )
            or WB_TOKEN_FILE.exists()
        ),
    }


@app.post("/run", response_model=AgentRunResult)
async def run(
    req: AgentRunRequest,
    authorization: str | None = Header(None),
):
    if not verify_bearer(RUNNER_TOKEN, authorization):
        raise HTTPException(401, "invalid runner token")
    if req.agent != "workbuddy":
        raise HTTPException(
            400,
            "workbuddy runner only accepts workbuddy tasks",
        )
    if ALLOWED_REPO and req.repository != ALLOWED_REPO:
        raise HTTPException(403, "repository not allowed")

    wb = WorkBuddyClient()

    try:
        if req.source_kind == "issue":
            output = await wb.run_cloud_task(
                specification_prompt(req),
                f"Spec {req.task_id}",
            )
            obj = parse_json_object(output)
            summary, changes = validate_spec_result(obj)
            artifacts = [change.path for change in changes]
            return AgentRunResult(
                status="success",
                summary=summary,
                artifacts=artifacts,
                changes=changes,
                handoff=Handoff(
                    task_id=req.task_id,
                    from_agent="workbuddy",
                    to_agent="sandbox",
                    phase="specification",
                    status="success",
                    summary=summary,
                    artifacts=artifacts,
                ),
            )

        output = await wb.run_cloud_task(
            final_review_prompt(req),
            f"Review {req.task_id} PR {req.source_number}",
        )
        obj = parse_json_object(output)
        status = str(obj.get("status") or "").lower()
        summary = str(
            obj.get("summary") or "WorkBuddy returned no summary"
        )
        if status == "success":
            return AgentRunResult(
                status="success",
                summary=summary,
                handoff=Handoff(
                    task_id=req.task_id,
                    from_agent="workbuddy",
                    to_agent="human",
                    phase="product_review",
                    status="success",
                    summary=summary,
                    source_ref=req.source_ref,
                    source_sha=req.source_sha,
                    pr_number=req.source_number,
                ),
            )
        return AgentRunResult(
            status="blocked",
            summary=summary,
            handoff=Handoff(
                task_id=req.task_id,
                from_agent="workbuddy",
                to_agent="human",
                phase="product_review",
                status="blocked",
                summary=summary,
                blockers=[summary],
                source_ref=req.source_ref,
                source_sha=req.source_sha,
                pr_number=req.source_number,
            ),
        )

    except Exception as exc:
        summary = (
            "WorkBuddy integration failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return AgentRunResult(
            status="failed",
            summary=summary,
            handoff=Handoff(
                task_id=req.task_id,
                from_agent="workbuddy",
                to_agent="human",
                phase="specification" if req.source_kind == "issue" else "product_review",
                status="failed",
                summary=summary,
                blockers=[summary],
                source_ref=req.source_ref,
                source_sha=req.source_sha,
                pr_number=req.source_number if req.source_kind == "pull_request" else None,
            ),
        )
