from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException

from .models import AgentRunRequest, AgentRunResult
from .security import verify_bearer

RUNNER_TOKEN = os.getenv("WORKBUDDY_RUNNER_TOKEN", "")
ALLOWED_REPO = os.getenv("WORKBUDDY_ALLOWED_REPO", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

WB_BASE = os.getenv("WORKBUDDY_API_BASE", "https://www.workbuddy.cn/openapi/v2").rstrip("/")
WB_ACCESS_TOKEN = os.getenv("WORKBUDDY_ACCESS_TOKEN", "")
WB_REFRESH_TOKEN = os.getenv("WORKBUDDY_REFRESH_TOKEN", "")
WB_CLIENT_ID = os.getenv("WORKBUDDY_CLIENT_ID", "")
WB_CLIENT_SECRET = os.getenv("WORKBUDDY_CLIENT_SECRET", "")
WB_TOKEN_FILE = Path(os.getenv("WORKBUDDY_TOKEN_FILE", "/app/data/workbuddy_oauth.json"))
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
MAX_CONTEXT_CHARS = 80_000

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
            response = await client.request(method, url, headers=headers, **kwargs)
        if response.status_code == 401 and self.refresh_token:
            token = await self.refresh()
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
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
                raise RuntimeError(f"WorkBuddy task ended with status={status}")
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
            raise RuntimeError("WorkBuddy completed but did not return ACP link/token")

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
            raise RuntimeError("WorkBuddy task produced no overview artifact")
        candidates.sort(key=lambda item: item[0])
        return str(candidates[-1][1])


class GitHubRepo:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo
        self.base = f"https://api.github.com/repos/{repo}"

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.request(
                method, url, headers=self.headers(), **kwargs
            )
        response.raise_for_status()
        return response

    async def text_file(self, path: str, ref: str | None = None) -> str:
        params = {"ref": ref} if ref else None
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base}/contents/{path}",
                headers=self.headers(),
                params=params,
            )
        if response.status_code == 404:
            return ""
        response.raise_for_status()
        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data.get("content") or "").decode(
                "utf-8", "replace"
            )
        return ""

    async def create_spec_pr(
        self,
        issue_number: int,
        title: str,
        files: list[dict[str, str]],
    ) -> int:
        repo = (await self.request("GET", self.base)).json()
        default = repo["default_branch"]
        branch_info = (
            await self.request("GET", f"{self.base}/branches/{default}")
        ).json()
        base_sha = branch_info["commit"]["sha"]
        branch = f"agent/workbuddy/issue-{issue_number}-{uuid.uuid4().hex[:8]}"

        await self.request(
            "POST",
            f"{self.base}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )

        for item in files:
            path = item["path"]
            file_content = item["content"]
            get_url = f"{self.base}/contents/{path}"
            async with httpx.AsyncClient(timeout=30) as client:
                current = await client.get(
                    get_url,
                    headers=self.headers(),
                    params={"ref": branch},
                )
            body: dict[str, Any] = {
                "message": f"docs: WorkBuddy update {path}",
                "content": base64.b64encode(file_content.encode()).decode(),
                "branch": branch,
            }
            if current.status_code == 200:
                body["sha"] = current.json()["sha"]
            elif current.status_code != 404:
                current.raise_for_status()
            await self.request("PUT", get_url, json=body)

        pr = (
            await self.request(
                "POST",
                f"{self.base}/pulls",
                json={
                    "title": f"spec: {title[:180]}",
                    "head": branch,
                    "base": default,
                    "body": (
                        f"WorkBuddy product/specification handoff for issue "
                        f"#{issue_number}.\n\n"
                        f"Closes #{issue_number}\n\n"
                        "This PR must pass Sandbox QA, Codex implementation, "
                        "final QA, and human approval before merge."
                    ),
                },
            )
        ).json()
        return int(pr["number"])

    async def pr_context(self, number: int) -> str:
        pr = (await self.request("GET", f"{self.base}/pulls/{number}")).json()
        files = (
            await self.request(
                "GET",
                f"{self.base}/pulls/{number}/files",
                params={"per_page": 100},
            )
        ).json()
        parts = [
            f"PR #{number}: {pr.get('title', '')}",
            f"Base: {pr.get('base', {}).get('ref', '')}",
            f"Head: {pr.get('head', {}).get('ref', '')}",
            "",
            pr.get("body") or "",
            "",
            "Changed files:",
        ]
        used = sum(len(item) for item in parts)
        for file_item in files:
            patch = (file_item.get("patch") or "")[:5000]
            block = (
                f"\n### {file_item.get('filename')} "
                f"({file_item.get('status')})\n{patch}\n"
            )
            if used + len(block) > MAX_CONTEXT_CHARS:
                break
            parts.append(block)
            used += len(block)
        return "\n".join(parts)


def validate_spec_result(
    obj: dict[str, Any],
) -> tuple[str, list[dict[str, str]]]:
    status = str(obj.get("status") or "").lower()
    if status != "success":
        raise ValueError(
            obj.get("summary") or "WorkBuddy did not approve the specification"
        )
    raw = obj.get("files")
    if not isinstance(raw, list):
        raise ValueError("WorkBuddy JSON has no files array")

    files: list[dict[str, str]] = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid files item")
        path = str(item.get("path") or "")
        file_content = item.get("content")
        if path not in ALLOWED_SPEC_FILES:
            raise ValueError(f"Path not allowed: {path}")
        if not isinstance(file_content, str) or not file_content.strip():
            raise ValueError(f"Empty content for {path}")
        if len(file_content.encode()) > MAX_FILE_BYTES:
            raise ValueError(f"File too large: {path}")
        files.append({"path": path, "content": file_content})
        seen.add(path)

    missing = ALLOWED_SPEC_FILES - seen
    if missing:
        raise ValueError(
            "Missing required files: " + ", ".join(sorted(missing))
        )
    return str(
        obj.get("summary") or "WorkBuddy specification completed"
    ), files


def spec_prompt(req: AgentRunRequest, current_context: str) -> str:
    issue = req.payload.get("issue") or {}
    title = str(issue.get("title") or req.task_id)
    body = str(issue.get("body") or "")
    return f"""You are WorkBuddy, acting as the product/business specification agent.

Task: {title}

Issue body:
{body}

Repository context:
{current_context}

Produce the product/specification handoff for a multilingual Cambodia recruitment product.

Hard constraints:
- Default language is Khmer, then English, then Chinese.
- Paid employer features may improve discovery/filtering/reach, but payment must never directly increase relevance score.
- Use synthetic examples only; never invent real candidate personal data.
- Do not propose automatic production deployment or automatic merge to main.
- Do not request or expose secrets.

Return JSON ONLY, with exactly this shape:
{{
  "status": "success",
  "summary": "short summary",
  "files": [
    {{"path":"docs/PRD.md","content":"full markdown"}},
    {{"path":"docs/MATCHING_SPEC.md","content":"full markdown"}},
    {{"path":"docs/I18N.md","content":"full markdown"}},
    {{"path":"docs/MONETIZATION.md","content":"full markdown"}},
    {{"path":"TASKS.md","content":"full markdown"}}
  ]
}}

Do not include code fences or commentary outside the JSON.
"""


def review_prompt(context: str) -> str:
    return f"""You are WorkBuddy performing the final product/business review.

Review this pull request against the product requirements and safety boundaries.

{context}

Check:
- product requirements are represented coherently;
- Khmer default, English second, Chinese third;
- employer payment never directly changes relevance score;
- no production credentials or real candidate data were introduced;
- no automatic production deployment or main auto-merge was introduced.

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
            400, "workbuddy runner only accepts workbuddy tasks"
        )
    if ALLOWED_REPO and req.repository != ALLOWED_REPO:
        raise HTTPException(403, "repository not allowed")
    if not GITHUB_TOKEN:
        return AgentRunResult(
            status="blocked",
            summary="GITHUB_TOKEN is not configured",
        )

    wb = WorkBuddyClient()
    gh = GitHubRepo(GITHUB_TOKEN, req.repository)

    try:
        if req.source_kind == "issue":
            context_parts = []
            for path in ("README.md", "AGENTS.md", "TASKS.md"):
                text = await gh.text_file(path)
                if text:
                    context_parts.append(
                        f"## {path}\n{text[:20000]}"
                    )
            output = await wb.run_cloud_task(
                spec_prompt(req, "\n\n".join(context_parts)),
                f"Spec {req.task_id}",
            )
            obj = parse_json_object(output)
            summary, files = validate_spec_result(obj)
            issue = req.payload.get("issue") or {}
            pr_number = await gh.create_spec_pr(
                req.source_number,
                str(issue.get("title") or req.task_id),
                files,
            )
            return AgentRunResult(
                status="success",
                summary=summary,
                artifacts=[item["path"] for item in files],
                pr_number=pr_number,
            )

        context = await gh.pr_context(req.source_number)
        output = await wb.run_cloud_task(
            review_prompt(context),
            f"Review PR {req.source_number}",
        )
        obj = parse_json_object(output)
        status = str(obj.get("status") or "").lower()
        summary = str(
            obj.get("summary") or "WorkBuddy returned no summary"
        )
        if status == "success":
            return AgentRunResult(status="success", summary=summary)
        return AgentRunResult(status="blocked", summary=summary)

    except Exception as exc:
        return AgentRunResult(
            status="failed",
            summary=(
                "WorkBuddy integration failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )
