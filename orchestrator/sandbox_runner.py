from __future__ import annotations

import asyncio
import base64
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from .models import AgentRunRequest, AgentRunResult
from .security import verify_bearer

TOKEN=os.getenv("SANDBOX_RUNNER_TOKEN","")
ALLOWED_REPO=os.getenv("SANDBOX_ALLOWED_REPO","")
GITHUB_TOKEN=os.getenv("GITHUB_TOKEN","")
TIMEOUT=int(os.getenv("SANDBOX_TIMEOUT_SECONDS","300"))
WORK_ROOT=os.getenv("SANDBOX_WORK_ROOT","/tmp/sandbox-work")

app=FastAPI(title="Sandbox QA Runner")

def git_env():
    env=os.environ.copy()
    if GITHUB_TOKEN:
        basic=base64.b64encode(f"x-access-token:{GITHUB_TOKEN}".encode()).decode()
        env["GIT_CONFIG_COUNT"]="1"
        env["GIT_CONFIG_KEY_0"]="http.https://github.com/.extraheader"
        env["GIT_CONFIG_VALUE_0"]=f"AUTHORIZATION: basic {basic}"
    return env

def clean_child_env(workspace:Path):
    env={}
    for k,v in os.environ.items():
        upper=k.upper()
        if any(marker in upper for marker in ("TOKEN","SECRET","PASSWORD","API_KEY","PRIVATE_KEY")):
            continue
        env[k]=v
    env["AGENT_WORKSPACE"]=str(workspace)
    return env

async def run_cmd(args:list[str],cwd:Path,env:dict[str,str],timeout:int=TIMEOUT):
    proc=await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out,_=await asyncio.wait_for(proc.communicate(),timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 124,"timeout"
    text=out.decode("utf-8","replace")
    return proc.returncode,text[-12000:]

@app.get("/healthz")
async def healthz():
    return {"ok":True,"agent":"sandbox","allowed_repo":ALLOWED_REPO}

@app.post("/run",response_model=AgentRunResult)
async def run(req:AgentRunRequest,authorization:str|None=Header(None)):
    if not verify_bearer(TOKEN,authorization):
        raise HTTPException(401,"invalid runner token")
    if req.agent!="sandbox":
        raise HTTPException(400,"sandbox runner only accepts sandbox tasks")
    if ALLOWED_REPO and req.repository!=ALLOWED_REPO:
        raise HTTPException(403,"repository not allowed")
    if req.source_kind!="pull_request":
        return AgentRunResult(
            status="blocked",
            summary="Sandbox QA requires a pull request so it can test an immutable PR revision.",
        )

    root=Path(WORK_ROOT)
    root.mkdir(parents=True,exist_ok=True)
    task_dir=Path(tempfile.mkdtemp(prefix=f"pr-{req.source_number}-",dir=str(root)))
    workspace=task_dir/"repo"
    try:
        code,out=await run_cmd(
            ["git","clone","--no-checkout",f"https://github.com/{req.repository}.git",str(workspace)],
            task_dir,
            git_env(),
        )
        if code!=0:
            return AgentRunResult(status="failed",summary=f"git clone failed: {out}")

        code,out=await run_cmd(
            ["git","fetch","origin",f"pull/{req.source_number}/head:agent-source"],
            workspace,
            git_env(),
        )
        if code!=0:
            return AgentRunResult(status="failed",summary=f"PR fetch failed: {out}")

        code,out=await run_cmd(["git","checkout","agent-source"],workspace,git_env())
        if code!=0:
            return AgentRunResult(status="failed",summary=f"checkout failed: {out}")

        child_env=clean_child_env(workspace)

        diff_code,diff_out=await run_cmd(["git","diff","--check"],workspace,child_env)
        if diff_code!=0:
            return AgentRunResult(
                status="blocked",
                summary="git diff --check failed:\n"+diff_out,
            )

        test_code,test_out=await run_cmd(
            ["python","-m","pytest","-q"],
            workspace,
            child_env,
        )
        if test_code!=0:
            return AgentRunResult(
                status="blocked",
                summary="Sandbox tests failed:\n"+test_out,
            )

        return AgentRunResult(
            status="success",
            summary="Sandbox QA passed.\n"+test_out[-4000:],
        )
    finally:
        shutil.rmtree(task_dir,ignore_errors=True)
