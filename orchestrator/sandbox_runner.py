from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

from .models import AgentRunRequest, AgentRunResult, CheckResult, Handoff
from .security import verify_bearer

TOKEN = os.getenv("SANDBOX_RUNNER_TOKEN", "")
ALLOWED_REPO = os.getenv("SANDBOX_ALLOWED_REPO", "")
TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "300"))
WORK_ROOT = os.getenv("SANDBOX_WORK_ROOT", "/tmp/sandbox-work")

SPEC_FILES = (
    "docs/PRD.md",
    "docs/MATCHING_SPEC.md",
    "docs/I18N.md",
    "docs/MONETIZATION.md",
    "TASKS.md",
)

app = FastAPI(title="Sandbox QA Runner")


def clean_env(workspace: Path) -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if any(
            marker in upper
            for marker in (
                "TOKEN",
                "SECRET",
                "PASSWORD",
                "API_KEY",
                "PRIVATE_KEY",
            )
        ):
            continue
        env[key] = value
    env["AGENT_WORKSPACE"] = str(workspace)
    return env


async def run_cmd(
    args: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: int = TIMEOUT,
):
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
    return process.returncode, output.decode(
        "utf-8",
        "replace",
    )[-12000:]


def blocked_handoff(
    req: AgentRunRequest,
    phase: str,
    summary: str,
    checks: list[CheckResult],
    status: str = "blocked",
) -> AgentRunResult:
    return AgentRunResult(
        status=status,
        summary=summary,
        checks=checks,
        handoff=Handoff(
            task_id=req.task_id,
            from_agent="sandbox",
            to_agent="human",
            phase=phase,
            status=status,
            summary=summary,
            checks=checks,
            blockers=[summary],
            source_ref=req.source_ref,
            source_sha=req.source_sha,
            pr_number=req.source_number,
        ),
    )


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "agent": "sandbox",
        "allowed_repo": ALLOWED_REPO,
        "github_auth_required_for_public_read": False,
    }


@app.post("/run", response_model=AgentRunResult)
async def run(
    req: AgentRunRequest,
    authorization: str | None = Header(None),
):
    if not verify_bearer(TOKEN, authorization):
        raise HTTPException(401, "invalid runner token")
    if req.agent != "sandbox":
        raise HTTPException(
            400,
            "sandbox runner only accepts sandbox tasks",
        )
    if ALLOWED_REPO and req.repository != ALLOWED_REPO:
        raise HTTPException(403, "repository not allowed")
    if req.source_kind != "pull_request":
        return AgentRunResult(
            status="blocked",
            summary="Sandbox QA requires a pull request.",
        )

    labels = {
        item.get("name")
        for item in (
            (req.payload.get("pull_request") or {}).get("labels") or []
        )
        if isinstance(item, dict)
    }
    final_gate = "needs:qa" in labels
    next_agent = "workbuddy" if final_gate else "codex"
    phase = "final_qa" if final_gate else "spec_qa"

    root = Path(WORK_ROOT)
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
        safe_env = clean_env(workspace)
        code, out = await run_cmd(
            [
                "git",
                "clone",
                "--no-checkout",
                f"https://github.com/{req.repository}.git",
                str(workspace),
            ],
            task_dir,
            safe_env,
        )
        checks.append(
            CheckResult(
                name="git_clone",
                status="passed" if code == 0 else "failed",
                detail=out,
            )
        )
        if code != 0:
            return blocked_handoff(
                req,
                phase,
                f"git clone failed: {out}",
                checks,
                status="failed",
            )

        code, out = await run_cmd(
            [
                "git",
                "fetch",
                "origin",
                f"pull/{req.source_number}/head:agent-source",
            ],
            workspace,
            safe_env,
        )
        checks.append(
            CheckResult(
                name="pr_fetch",
                status="passed" if code == 0 else "failed",
                detail=out,
            )
        )
        if code != 0:
            return blocked_handoff(
                req,
                phase,
                f"PR fetch failed: {out}",
                checks,
                status="failed",
            )

        target_revision = req.source_sha or "agent-source"
        code, out = await run_cmd(
            ["git", "checkout", "--detach", target_revision],
            workspace,
            safe_env,
        )
        if code != 0:
            return blocked_handoff(
                req,
                phase,
                f"checkout failed for {target_revision}: {out}",
                checks,
                status="failed",
            )

        code, actual_sha = await run_cmd(
            ["git", "rev-parse", "HEAD"],
            workspace,
            safe_env,
        )
        actual_sha = actual_sha.strip()
        revision_ok = code == 0 and (
            not req.source_sha or actual_sha == req.source_sha
        )
        checks.append(
            CheckResult(
                name="source_revision",
                status="passed" if revision_ok else "failed",
                detail=(
                    f"expected={req.source_sha or 'PR head'} "
                    f"actual={actual_sha}"
                ),
            )
        )
        if not revision_ok:
            return blocked_handoff(
                req,
                phase,
                "Sandbox checked out a different revision than the "
                "orchestrator supplied.",
                checks,
                status="failed",
            )

        missing = [
            path
            for path in SPEC_FILES
            if not (workspace / path).exists()
        ]
        checks.append(
            CheckResult(
                name="specification_artifacts",
                status="failed" if missing else "passed",
                detail=(
                    "missing: " + ", ".join(missing)
                    if missing
                    else "all required specification artifacts are present"
                ),
            )
        )
        if missing:
            return blocked_handoff(
                req,
                phase,
                "Required handoff artifacts are missing: "
                + ", ".join(missing),
                checks,
            )

        diff_code, diff_out = await run_cmd(
            ["git", "diff", "--check", "origin/main...HEAD"],
            workspace,
            safe_env,
        )
        checks.append(
            CheckResult(
                name="git_diff_check",
                status="passed" if diff_code == 0 else "failed",
                detail=diff_out,
            )
        )
        if diff_code != 0:
            return blocked_handoff(
                req,
                phase,
                "git diff --check failed:\n" + diff_out,
                checks,
            )

        if (workspace / "tests").exists():
            test_code, test_out = await run_cmd(
                ["python", "-m", "pytest", "-q"],
                workspace,
                safe_env,
            )
            checks.append(
                CheckResult(
                    name="pytest",
                    status="passed" if test_code == 0 else "failed",
                    detail=test_out,
                )
            )
            if test_code != 0:
                return blocked_handoff(
                    req,
                    phase,
                    "Sandbox tests failed:\n" + test_out,
                    checks,
                )
        else:
            checks.append(
                CheckResult(
                    name="pytest",
                    status="skipped",
                    detail="tests/ directory not present",
                )
            )

        summary = (
            "Sandbox final QA passed."
            if final_gate
            else "Sandbox specification QA passed."
        )
        return AgentRunResult(
            status="success",
            summary=summary,
            checks=checks,
            handoff=Handoff(
                task_id=req.task_id,
                from_agent="sandbox",
                to_agent=next_agent,
                phase=phase,
                status="success",
                summary=summary,
                artifacts=list(SPEC_FILES),
                checks=checks,
                source_ref=req.source_ref,
                source_sha=actual_sha,
                pr_number=req.source_number,
            ),
        )
    finally:
        shutil.rmtree(task_dir, ignore_errors=True)
