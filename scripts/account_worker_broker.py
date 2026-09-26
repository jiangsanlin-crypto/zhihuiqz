"""Translate trusted owner comments into shared-controller lease operations.

The broker never changes GitHub workflow labels. It derives acquire bindings from
the live PR and sends only authenticated requests to the controller.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import httpx

try:
    from scripts.shared_transport import request as control_request
except ModuleNotFoundError:
    from shared_transport import request as control_request

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
OWNER = os.environ["REPOSITORY_OWNER"]
EXPECTED_CONTROL_SHA = os.environ.get("EXPECTED_CONTROL_SHA", "")
API = "https://api.github.com"
MARKER = "<!-- shared-control-request:v1 -->"
TASK_RE = re.compile(r"<!-- agent-task-id:([A-Za-z0-9._:-]+) -->")


def gh(path: str):
    response = httpx.get(
        API + "/repos/" + REPO + "/" + path.lstrip("/"),
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
        follow_redirects=False,
    )
    response.raise_for_status()
    return response.json()


def ensure_controller_identity() -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", EXPECTED_CONTROL_SHA):
        raise ValueError("expected controller SHA is unavailable")
    identity = control_request("GET", "/readyz")
    if (
        not isinstance(identity, dict)
        or identity.get("repository") != REPO
        or identity.get("build_sha") != EXPECTED_CONTROL_SHA
        or identity.get("protocol") != "shared-claims:v1"
        or identity.get("writes_enabled") is not True
        or identity.get("agents_enabled") is not False
    ):
        raise RuntimeError("controller identity does not match trusted default branch")


def parse_request(text: str) -> dict:
    if MARKER not in text:
        raise ValueError("request marker missing")
    fenced = re.search(r"~~~json\s*(\{.*?\})\s*~~~", text, re.S)
    if fenced is None:
        fence = chr(96) * 3
        fenced = re.search(re.escape(fence) + r"json\s*(\{.*?\})\s*" + re.escape(fence), text, re.S)
    if fenced is None:
        raise ValueError("JSON request block missing")
    value = json.loads(fenced.group(1))
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def owned(value: dict) -> dict:
    keys = ("delivery_id", "lease_id", "worker_id")
    result = {key: str(value.get(key) or "") for key in keys}
    if not all(result.values()):
        raise ValueError("owned request is incomplete")
    return result


def acquire(pr_number: int, request: dict) -> dict:
    pr = gh(f"pulls/{pr_number}")
    if pr.get("state") != "open" or pr.get("merged_at"):
        raise ValueError("PR is not open")
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    if (
        (head.get("repo") or {}).get("full_name") != REPO
        or not head.get("sha")
        or not head.get("ref")
        or head.get("ref") in {"main", base.get("ref")}
    ):
        raise ValueError("unsafe PR branch identity")
    matches = set(TASK_RE.findall(str(pr.get("body") or "")))
    if len(matches) != 1:
        raise ValueError("stable task ID is ambiguous")
    phase = str(request.get("phase") or "")
    if phase not in {"phase:implementation", "phase:code-review", "phase:escalation-repair"}:
        raise ValueError("account worker phase is not supported")
    worker_id = str(request.get("worker_id") or "")
    request_id = str(request.get("request_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,150}", worker_id):
        raise ValueError("invalid worker_id")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,150}", request_id):
        raise ValueError("invalid request_id")
    payload = {
        "repository": REPO,
        "pr_number": pr_number,
        "source_sha": head["sha"],
        "head_ref": head["ref"],
        "task_id": next(iter(matches)),
        "phase": phase,
        "worker_id": worker_id,
        "request_id": request_id,
    }
    receipt = control_request("POST", "/claims/acquire", payload)
    claim = {
        "delivery_id": receipt["delivery_id"],
        "lease_id": receipt["lease_id"],
        "worker_id": worker_id,
    }
    started = control_request("POST", "/claims/start", claim)
    return {
        "status": "granted",
        "action": "acquire",
        "request_id": request_id,
        "phase": phase,
        "task_id": payload["task_id"],
        "pr_number": pr_number,
        "source_sha": str(started.get("source_sha") or receipt["source_sha"]),
        "delivery_id": claim["delivery_id"],
        "lease_id": claim["lease_id"],
        "worker_id": worker_id,
        "lease_expires_at": str(started.get("lease_expires_at") or receipt.get("lease_expires_at") or ""),
    }


def execute(pr_number: int, request: dict) -> dict:
    action = str(request.get("action") or "")
    if action == "acquire":
        return acquire(pr_number, request)

    claim = owned(request)
    if action == "heartbeat":
        result = control_request("POST", "/claims/heartbeat", claim)
    elif action == "prepare_head":
        target = str(request.get("target_sha") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", target):
            raise ValueError("invalid target_sha")
        result = control_request(
            "POST", "/claims/prepare-head", {**claim, "target_sha": target}
        )
    elif action == "confirm_head":
        result = control_request("POST", "/claims/confirm-head", claim)
    elif action == "advance":
        result = control_request("POST", "/claims/advance", claim)
    elif action == "release":
        result = control_request("POST", "/claims/release", claim)
    elif action == "decision":
        decision = str(request.get("decision") or "")
        code = str(request.get("reason_code") or "")
        if decision not in {"retry", "block", "repair"}:
            raise ValueError("invalid worker decision")
        if not re.fullmatch(r"[A-Z0-9_]{2,80}", code):
            raise ValueError("invalid reason_code")
        result = control_request(
            "POST",
            "/claims/decision",
            {**claim, "decision": decision, "reason_code": code},
        )
    else:
        raise ValueError("unsupported control action")
    return {
        "status": "ok",
        "action": action,
        "request_id": str(request.get("request_id") or ""),
        "pr_number": pr_number,
        **{
            key: value
            for key, value in result.items()
            if key in {"source_sha", "lease_expires_at", "released", "status"}
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comment-file", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.author != OWNER:
        raise SystemExit("only repository owner control requests are accepted")
    try:
        ensure_controller_identity()
        request = parse_request(Path(args.comment_file).read_text())
        result = execute(args.pr_number, request)
    except Exception as exc:
        result = {
            "status": "blocked",
            "action": "unknown",
            "request_id": "",
            "pr_number": args.pr_number,
            "reason": type(exc).__name__,
        }
        Path(args.output).write_text(json.dumps(result, sort_keys=True))
        raise
    Path(args.output).write_text(json.dumps(result, sort_keys=True))
    print(json.dumps({"status": result["status"], "action": result["action"]}))


if __name__ == "__main__":
    main()
