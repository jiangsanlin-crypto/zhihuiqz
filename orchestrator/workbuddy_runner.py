from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException

from .models import (
    AgentRunRequest,
    AgentRunResult,
    CheckResult,
    FileChange,
    Handoff,
)
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

EXPECTED_MODEL = os.getenv("WORKBUDDY_MODEL", "GLM-5.3-Flash")
MODEL_LOCK_CONFIRMED = os.getenv(
    "WORKBUDDY_MODEL_LOCK_CONFIRMED",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}

MAX_FILE_BYTES = 120_000
MAX_TEST_OUTPUT = 12_000

PROTOTYPE_FILES = {
    "reports/prototype_review.md",
    "reports/data_analysis.md",
    "reports/classification_validation.md",
    "reports/uiux_prototype.md",
}

QA_FILES = {
    "reports/test_report.md",
    "reports/uiux_acceptance.md",
    "reports/classification_validation.md",
    "reports/qa_summary.json",
}

DEPLOY_FILES = {
    "reports/deployment_plan.md",
    "reports/deployment_gate.json",
}

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
                self.access_token = (
                    data.get("access_token") or self.access_token
                )
                self.refresh_token = (
                    data.get("refresh_token") or self.refresh_token
                )
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
        if not (
            self.refresh_token
            and WB_CLIENT_ID
            and WB_CLIENT_SECRET
        ):
            if self.access_token:
                return self.access_token
            raise RuntimeError(
                "WorkBuddy OAuth is not configured."
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
        self.refresh_token = (
            data.get("refresh_token") or self.refresh_token
        )
        self.expires_at = (
            time.time()
            + int(data.get("expires_in") or 3600)
            - 60
        )
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
            self.expires_at == 0
            or self.expires_at > time.time() + 60
        ):
            return self.access_token
        return await self.refresh()

    async def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
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
            json={
                "prompt": prompt,
                "name": name[:120],
            },
            headers={"Content-Type": "application/json"},
        )
        task = unwrap(response.json())
        task_id = str(task["task_id"])
        deadline = time.monotonic() + WB_TIMEOUT
        last = task

        while time.monotonic() < deadline:
            status = str(last.get("status") or "").lower()
            if status == "completed":
                break
            if status in {"failed", "archived", "deleted"}:
                raise RuntimeError(
                    f"WorkBuddy task ended with status={status}"
                )
            await asyncio.sleep(WB_POLL)
            query = await self.request(
                "GET",
                f"{WB_BASE}/tasks/{task_id}",
            )
            last = unwrap(query.json())
        else:
            raise RuntimeError("WorkBuddy cloud task timed out")

        link = last.get("link") or task.get("link")
        ticket = last.get("token") or task.get("token")

        if not link or not ticket:
            query = await self.request(
                "GET",
                f"{WB_BASE}/tasks/{task_id}",
            )
            last = unwrap(query.json())
            link = last.get("link")
            ticket = last.get("token")

        if not link or not ticket:
            raise RuntimeError(
                "WorkBuddy completed without ACP link/token"
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
            if (
                artifact.get("type") == "overview"
                and artifact.get("text")
            ):
                candidates.append(
                    (
                        artifact.get("updatedAt") or 0,
                        artifact["text"],
                    )
                )

        if not candidates:
            raise RuntimeError(
                "WorkBuddy task produced no overview artifact"
            )

        candidates.sort(key=lambda item: item[0])
        return str(candidates[-1][1])


def validate_files(
    obj: dict[str, Any],
    allowed: set[str],
) -> tuple[str, list[FileChange]]:
    status = str(obj.get("status") or "").lower()
    if status not in {"success", "blocked"}:
        raise ValueError("status must be success or blocked")

    raw = obj.get("files")
    if not isinstance(raw, list):
        raise ValueError("WorkBuddy JSON has no files array")

    changes: list[FileChange] = []
    seen = set()

    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("invalid files item")

        path = str(item.get("path") or "")
        file_content = item.get("content")

        if path not in allowed:
            raise ValueError(f"path not allowed: {path}")
        if not isinstance(file_content, str) or not file_content.strip():
            raise ValueError(f"empty content for {path}")
        if len(file_content.encode()) > MAX_FILE_BYTES:
            raise ValueError(f"file too large: {path}")

        changes.append(
            FileChange(
                path=path,
                content=file_content,
                purpose=str(item.get("purpose") or ""),
            )
        )
        seen.add(path)

    missing = allowed - seen
    if missing:
        raise ValueError(
            "missing required files: "
            + ", ".join(sorted(missing))
        )

    summary = str(
        obj.get("summary")
        or "WorkBuddy phase completed"
    )
    return status + "\n" + summary, changes


async def run_cmd(
    args: list[str],
    cwd: Path,
    timeout: int = 300,
) -> tuple[int, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not any(
            marker in key.upper()
            for marker in (
                "TOKEN",
                "SECRET",
                "PASSWORD",
                "API_KEY",
                "PRIVATE_KEY",
            )
        )
    }

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return 124, "timeout"

    return (
        process.returncode,
        output.decode("utf-8", "replace")[-MAX_TEST_OUTPUT:],
    )


async def local_qa(req: AgentRunRequest) -> list[CheckResult]:
    root = Path("/tmp/workbuddy-qa")
    root.mkdir(parents=True, exist_ok=True)
    task_dir = Path(
        tempfile.mkdtemp(
            prefix=f"pr-{req.source_number}-",
            dir=str(root),
        )
    )
    workspace = task_dir / "repo"
    checks: list[CheckResult] = []

    try:
        code, out = await run_cmd(
            [
                "git",
                "clone",
                "--no-checkout",
                f"https://github.com/{req.repository}.git",
                str(workspace),
            ],
            task_dir,
        )
        checks.append(
            CheckResult(
                name="git_clone",
                status="passed" if code == 0 else "failed",
                detail=out,
            )
        )
        if code != 0:
            return checks

        code, out = await run_cmd(
            [
                "git",
                "fetch",
                "origin",
                f"pull/{req.source_number}/head:agent-source",
            ],
            workspace,
        )
        checks.append(
            CheckResult(
                name="pr_fetch",
                status="passed" if code == 0 else "failed",
                detail=out,
            )
        )
        if code != 0:
            return checks

        revision = req.source_sha or "agent-source"
        code, out = await run_cmd(
            ["git", "checkout", "--detach", revision],
            workspace,
        )
        checks.append(
            CheckResult(
                name="checkout",
                status="passed" if code == 0 else "failed",
                detail=out,
            )
        )
        if code != 0:
            return checks

        code, out = await run_cmd(
            ["git", "diff", "--check", "origin/main...HEAD"],
            workspace,
        )
        checks.append(
            CheckResult(
                name="git_diff_check",
                status="passed" if code == 0 else "failed",
                detail=out,
            )
        )

        if (workspace / "tests").exists():
            code, out = await run_cmd(
                ["python", "-m", "pytest", "-q"],
                workspace,
            )
            checks.append(
                CheckResult(
                    name="pytest",
                    status="passed" if code == 0 else "failed",
                    detail=out,
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="pytest",
                    status="skipped",
                    detail="tests/ directory not present",
                )
            )

        return checks
    finally:
        shutil.rmtree(task_dir, ignore_errors=True)


def prototype_prompt(req: AgentRunRequest) -> str:
    repo_url = f"https://github.com/{req.repository}"
    pr_url = f"{repo_url}/pull/{req.source_number}"

    return f"""You are WorkBuddy.

Role for this phase:
- prototype engineer
- data analyst
- recruitment classification validation engineer
- UI/UX prototype reviewer

Expected model: {EXPECTED_MODEL}

The repository and PR are public. Read them directly without asking for
GitHub OAuth or GitHub tokens.

Task ID: {req.task_id}
Repository: {repo_url}
PR: {pr_url}

Read:
- PR body and prior agent-handoff comments
- docs/PRD.md
- docs/RECRUITMENT_RULES.md
- docs/DATA_COLLECTION_PLAN.md
- docs/CLASSIFICATION_DICTIONARY.md
- TASKS.md
- current prototype/code if present

Review Cambodia recruitment requirements, Khmer terminology, data fields,
classification logic, prototype usability, and testability.

Return JSON ONLY:
{{
  "status": "success" or "blocked",
  "summary": "short conclusion",
  "files": [
    {{"path":"reports/prototype_review.md","content":"full markdown","purpose":"prototype review"}},
    {{"path":"reports/data_analysis.md","content":"full markdown","purpose":"data analysis"}},
    {{"path":"reports/classification_validation.md","content":"full markdown","purpose":"classification validation"}},
    {{"path":"reports/uiux_prototype.md","content":"full markdown","purpose":"UI/UX prototype review"}}
  ]
}}

If there is a blocker, still produce all four files and explain the blocker.
Do not modify source code. Do not deploy. Do not request secrets.
"""


def qa_prompt(
    req: AgentRunRequest,
    checks: list[CheckResult],
) -> str:
    repo_url = f"https://github.com/{req.repository}"
    pr_url = f"{repo_url}/pull/{req.source_number}"
    test_summary = "\n\n".join(
        f"{item.name}: {item.status}\n{item.detail[-3000:]}"
        for item in checks
    )

    return f"""You are WorkBuddy.

Role for this phase:
- classification algorithm validation engineer
- test engineer
- Khmer/English/Chinese UI reviewer
- UI/UX acceptance engineer

Expected model: {EXPECTED_MODEL}

Task ID: {req.task_id}
Repository: {repo_url}
PR: {pr_url}

Read the public PR directly and inspect all prior agent-handoff comments.
Compare the implementation against the Codex product specification and the
prototype-validation reports.

Deterministic test evidence from the local QA harness:
{test_summary}

Return JSON ONLY:
{{
  "status": "success" or "blocked",
  "summary": "acceptance conclusion",
  "files": [
    {{"path":"reports/test_report.md","content":"full markdown","purpose":"test evidence"}},
    {{"path":"reports/uiux_acceptance.md","content":"full markdown","purpose":"UI/UX acceptance"}},
    {{"path":"reports/classification_validation.md","content":"full markdown","purpose":"final classification validation"}},
    {{"path":"reports/qa_summary.json","content":"valid JSON text","purpose":"machine-readable QA summary"}}
  ]
}}

Any failed deterministic test must result in status=blocked.
Do not deploy production. Do not request secrets.
"""


def deploy_prompt(req: AgentRunRequest) -> str:
    repo_url = f"https://github.com/{req.repository}"
    pr_url = f"{repo_url}/pull/{req.source_number}"

    return f"""You are WorkBuddy.

Role for this phase:
- production deployment engineer
- release deployment reviewer
- rollback planner
- health-check owner

Expected model: {EXPECTED_MODEL}

Task ID: {req.task_id}
Repository: {repo_url}
PR: {pr_url}

Read the public PR directly and inspect:
- all prior agent-handoff comments;
- reports/release_gate.json;
- docs/RELEASE_NOTES.md;
- reports/test_report.md;
- reports/uiux_acceptance.md;
- reports/classification_validation.md;
- deployment documentation and Docker configuration.

This system is configured for fully automatic delivery. Do not request a human
approval step. Instead, decide whether deployment is safe based on the
documented gates.

Return JSON ONLY:
{{
  "status": "success" or "blocked",
  "summary": "deployment readiness conclusion",
  "files": [
    {{"path":"reports/deployment_plan.md","content":"full markdown deployment and rollback plan","purpose":"deployment plan"}},
    {{"path":"reports/deployment_gate.json","content":"valid JSON text with status ready or blocked","purpose":"machine-readable deployment gate"}}
  ]
}}

A successful result means:
- release gate is ready;
- previous QA is successful;
- no unresolved blocker exists;
- rollback procedure is defined;
- deployment can proceed automatically.

Do not expose secrets. Do not execute SSH yourself. GitHub Actions performs the
actual merge/deployment commands after this gate succeeds.
"""


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "agent": "workbuddy",
        "allowed_repo": ALLOWED_REPO,
        "github_auth_required_for_public_read": False,
        "oauth_configured": bool(
            WB_ACCESS_TOKEN
            or (
                WB_REFRESH_TOKEN
                and WB_CLIENT_ID
                and WB_CLIENT_SECRET
            )
            or WB_TOKEN_FILE.exists()
        ),
        "expected_model": EXPECTED_MODEL,
        "model_lock_confirmed": MODEL_LOCK_CONFIRMED,
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
            "workbuddy runner only accepts WorkBuddy tasks",
        )
    if ALLOWED_REPO and req.repository != ALLOWED_REPO:
        raise HTTPException(403, "repository not allowed")
    if EXPECTED_MODEL != "GLM-5.3-Flash" or not MODEL_LOCK_CONFIRMED:
        return AgentRunResult(
            status="blocked",
            summary=(
                "WorkBuddy model lock is not confirmed. Configure the dedicated "
                "WorkBuddy app to expose only GLM-5.3-Flash, then set "
                "WORKBUDDY_MODEL_LOCK_CONFIRMED=true."
            ),
        )

    wb = WorkBuddyClient()

    try:
        if req.phase == "phase:prototype":
            output = await wb.run_cloud_task(
                prototype_prompt(req),
                f"Prototype validation {req.task_id}",
            )
            obj = parse_json_object(output)
            packed, changes = validate_files(
                obj,
                PROTOTYPE_FILES,
            )
            status, summary = packed.split("\n", 1)

            return AgentRunResult(
                status=status,
                summary=summary,
                artifacts=[change.path for change in changes],
                changes=changes,
                handoff=Handoff(
                    task_id=req.task_id,
                    from_agent="workbuddy",
                    to_agent="chatgpt" if status == "success" else "human",
                    phase="prototype_validation",
                    status=status,
                    summary=summary,
                    model=EXPECTED_MODEL,
                    effort="workbuddy-configured",
                    required_inputs=[
                        "Codex product specification",
                        "public PR",
                        "prior agent handoffs",
                    ],
                    expected_outputs=sorted(PROTOTYPE_FILES),
                    artifacts=[change.path for change in changes],
                    blockers=[] if status == "success" else [summary],
                    source_ref=req.source_ref,
                    source_sha=req.source_sha,
                    pr_number=req.source_number,
                ),
            )

        if req.phase == "phase:qa":
            checks = await local_qa(req)
            deterministic_failed = any(
                item.status == "failed"
                for item in checks
            )

            output = await wb.run_cloud_task(
                qa_prompt(req, checks),
                f"QA acceptance {req.task_id}",
            )
            obj = parse_json_object(output)
            packed, changes = validate_files(
                obj,
                QA_FILES,
            )
            status, summary = packed.split("\n", 1)

            if deterministic_failed:
                status = "blocked"
                summary = (
                    "Deterministic QA failed; WorkBuddy acceptance is blocked. "
                    + summary
                )

            return AgentRunResult(
                status=status,
                summary=summary,
                artifacts=[change.path for change in changes],
                changes=changes,
                checks=checks,
                handoff=Handoff(
                    task_id=req.task_id,
                    from_agent="workbuddy",
                    to_agent="codex" if status == "success" else "human",
                    phase="qa_acceptance",
                    status=status,
                    summary=summary,
                    model=EXPECTED_MODEL,
                    effort="workbuddy-configured",
                    required_inputs=[
                        "ChatGPT implementation",
                        "Codex specification",
                        "prototype-validation reports",
                        "deterministic test evidence",
                    ],
                    expected_outputs=sorted(QA_FILES),
                    artifacts=[change.path for change in changes],
                    checks=checks,
                    blockers=[] if status == "success" else [summary],
                    source_ref=req.source_ref,
                    source_sha=req.source_sha,
                    pr_number=req.source_number,
                ),
            )

        if req.phase == "phase:deploy":
            output = await wb.run_cloud_task(
                deploy_prompt(req),
                f"Deployment readiness {req.task_id}",
            )
            obj = parse_json_object(output)
            packed, changes = validate_files(
                obj,
                DEPLOY_FILES,
            )
            status, summary = packed.split("\n", 1)

            gate_change = next(
                change for change in changes
                if change.path == "reports/deployment_gate.json"
            )
            try:
                gate = json.loads(gate_change.content)
            except json.JSONDecodeError as exc:
                raise ValueError("deployment_gate.json is invalid JSON") from exc

            if gate.get("status") != "ready":
                status = "blocked"
                summary = (
                    "WorkBuddy deployment gate is not ready. "
                    + summary
                )

            return AgentRunResult(
                status=status,
                summary=summary,
                artifacts=[change.path for change in changes],
                changes=changes,
                handoff=Handoff(
                    task_id=req.task_id,
                    from_agent="workbuddy",
                    to_agent="workbuddy" if status == "success" else "human",
                    phase="deployment_plan",
                    status=status,
                    summary=summary,
                    model=EXPECTED_MODEL,
                    effort="workbuddy-configured",
                    required_inputs=[
                        "Codex release gate",
                        "release notes",
                        "WorkBuddy QA reports",
                        "public PR",
                        "deployment configuration",
                    ],
                    expected_outputs=sorted(DEPLOY_FILES),
                    acceptance=[
                        "deployment gate status must be ready",
                        "rollback plan must be defined",
                        "GitHub Actions performs merge/deployment",
                    ],
                    artifacts=[change.path for change in changes],
                    blockers=[] if status == "success" else [summary],
                    source_ref=req.source_ref,
                    source_sha=req.source_sha,
                    pr_number=req.source_number,
                ),
            )

        return AgentRunResult(
            status="blocked",
            summary=f"unsupported WorkBuddy phase: {req.phase}",
        )

    except Exception as exc:
        summary = (
            "WorkBuddy phase failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return AgentRunResult(
            status="failed",
            summary=summary,
            handoff=Handoff(
                task_id=req.task_id,
                from_agent="workbuddy",
                to_agent="human",
                phase=(
                    "prototype_validation"
                    if req.phase == "phase:prototype"
                    else "qa_acceptance"
                    if req.phase == "phase:qa"
                    else "deployment_plan"
                    if req.phase == "phase:deploy"
                    else "workbuddy"
                ),
                status="failed",
                summary=summary,
                model=EXPECTED_MODEL,
                effort="workbuddy-configured",
                blockers=[summary],
                source_ref=req.source_ref,
                source_sha=req.source_sha,
                pr_number=req.source_number,
            ),
        )
