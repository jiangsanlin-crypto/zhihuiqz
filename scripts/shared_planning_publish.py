"""Shared Codex planning publication executor.

This is a content publisher, not a workflow-state writer. The controller owns
leases and the initial PR state projection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote

import httpx

try:
    from scripts.shared_transport import request as control_request
except ModuleNotFoundError:
    from shared_transport import request as control_request

REPO = os.environ.get("GITHUB_REPOSITORY", "jiangsanlin-crypto/zhihuiqz")
TOKEN = os.environ.get("GH_TOKEN", "")
API = "https://api.github.com"
ALLOWED = {
    "docs/PRD.md",
    "docs/RECRUITMENT_RULES.md",
    "docs/DATA_COLLECTION_PLAN.md",
    "docs/CLASSIFICATION_DICTIONARY.md",
    "TASKS.md",
    "CHANGELOG.md",
}


def gh(method: str, path: str, payload=None, *, params=None, allow_404=False):
    if not TOKEN:
        raise RuntimeError("GitHub automation token is unavailable")
    suffix = "/" + path.lstrip("/") if path else ""
    response = httpx.request(
        method,
        API + "/repos/" + REPO + suffix,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json=payload,
        params=params,
        timeout=60,
        follow_redirects=False,
    )
    if allow_404 and response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json() if response.content else {}


def issue_data(number: int):
    return gh("GET", f"issues/{number}")


def body_for(number: int) -> str:
    return (
        f"<!-- agent-task-id:GH-ISSUE-{number} -->\n\n"
        f"Shared Codex product-planning output for issue #{number}.\n\n"
        "Next owner: validation prototype/data/classification gate.\n\n"
        f"Closes #{number}\n"
    )


def changed_files() -> list[str]:
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only"], text=True
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], text=True
    ).splitlines()
    paths = sorted({p.strip() for p in tracked + untracked if p.strip()})
    if not paths:
        raise RuntimeError("Codex produced no product planning changes")
    outside = [p for p in paths if p not in ALLOWED]
    if outside:
        raise RuntimeError("Codex changed files outside planning allowlist")
    for path in paths:
        if not Path(path).is_file():
            raise RuntimeError("planning artifact missing from workspace")
    return paths


def create_plan_commit(paths: list[str], issue_number: int) -> tuple[str, str]:
    repo = gh("GET", "")
    base_ref = str(repo["default_branch"])
    base = gh("GET", f"git/ref/heads/{quote(base_ref, safe='')}")
    base_sha = str(base["object"]["sha"])
    workspace_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    if base_sha != workspace_sha:
        raise RuntimeError("default branch advanced during planning; retry on the new controller build")
    parent = gh("GET", f"git/commits/{base_sha}")
    entries = []
    for path in paths:
        file_content = Path(path).read_text()
        blob = gh(
            "POST", "git/blobs", {"content": file_content, "encoding": "utf-8"}
        )
        entries.append(
            {"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}
        )
    tree = gh(
        "POST",
        "git/trees",
        {"base_tree": parent["tree"]["sha"], "tree": entries},
    )
    commit = gh(
        "POST",
        "git/commits",
        {
            "message": f"docs: shared Codex product plan for issue #{issue_number}",
            "tree": tree["sha"],
            "parents": [base_sha],
        },
    )
    return str(commit["sha"]), base_ref


def ensure_branch(branch: str, sha: str) -> None:
    live = gh("GET", f"git/ref/heads/{quote(branch, safe='')}", allow_404=True)
    if live is None:
        gh("POST", "git/refs", {"ref": "refs/heads/" + branch, "sha": sha})
        return
    if str(live["object"]["sha"]) != sha:
        raise RuntimeError("reserved planning branch points to another SHA")


def branch_prs(branch: str):
    owner = REPO.split("/", 1)[0]
    return gh(
        "GET",
        "pulls",
        params={"state": "all", "head": f"{owner}:{branch}", "per_page": 100},
    )


def ensure_pr(number: int, branch: str, base_ref: str, sha: str) -> int:
    all_prs = branch_prs(branch)
    open_prs = [p for p in all_prs if p.get("state") == "open"]
    if len(all_prs) > 1 or (all_prs and not open_prs):
        raise RuntimeError("planning branch has historical/ambiguous PR publication")
    if open_prs:
        pr = open_prs[0]
    else:
        issue = issue_data(number)
        pr = gh(
            "POST",
            "pulls",
            {
                "title": "spec: " + str(issue.get("title") or f"Issue {number}"),
                "head": branch,
                "base": base_ref,
                "body": body_for(number),
                "maintainer_can_modify": True,
            },
        )
    pr = gh("GET", f"pulls/{int(pr['number'])}")
    if (
        str((pr.get("head") or {}).get("sha")) != sha
        or str((pr.get("head") or {}).get("ref")) != branch
        or str((pr.get("base") or {}).get("ref")) != base_ref
        or str(pr.get("body") or "") != body_for(number)
    ):
        raise RuntimeError("published PR does not match reserved intent")
    return int(pr["number"])


def commit_artifacts(sha: str) -> list[str]:
    commit = gh("GET", f"commits/{sha}", params={"per_page": 100})
    paths = sorted(
        {
            str(item.get("filename"))
            for item in commit.get("files", [])
            if item.get("filename")
        }
    )
    if not paths or not set(paths) <= ALLOWED:
        raise RuntimeError("planning commit artifacts are invalid")
    return paths


def ensure_handoff(pr_number: int, issue_number: int, branch: str, sha: str, artifacts):
    comments = gh(
        "GET", f"issues/{pr_number}/comments", params={"per_page": 100}
    )
    marker = "<!-- agent-handoff:v1 -->"
    for item in comments:
        body = str(item.get("body") or "")
        if (
            marker in body
            and f'"task_id": "GH-ISSUE-{issue_number}"' in body
            and f'"source_sha": "{sha}"' in body
            and '"from_agent": "codex"' in body
            and '"phase": "product_planning"' in body
        ):
            return
    payload = {
        "version": "1.0",
        "task_id": f"GH-ISSUE-{issue_number}",
        "from_agent": "codex",
        "to_agent": "workbuddy",
        "phase": "product_planning",
        "status": "success",
        "summary": "Shared-controller Codex product plan completed.",
        "model": "gpt-6-luna",
        "effort": "high",
        "required_inputs": ["source issue", "public repository"],
        "expected_outputs": [
            "reports/prototype_review.md",
            "reports/data_analysis.md",
            "reports/classification_validation.md",
            "reports/uiux_prototype.md",
        ],
        "acceptance": [
            "prototype validation must pass before implementation"
        ],
        "artifacts": artifacts,
        "checks": [
            {
                "name": "shared_planning_publication",
                "status": "passed",
                "detail": "immutable plan commit and PR publication verified",
            }
        ],
        "blockers": [],
        "source_ref": branch,
        "source_sha": sha,
        "pr_number": pr_number,
    }
    fence = chr(96) * 3
    body = (
        marker
        + "\n### Agent handoff: codex → workbuddy\n\n"
        + fence + "json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n" + fence + "\n"
    )
    gh("POST", f"issues/{pr_number}/comments", {"body": body})


def heartbeat(claim: dict) -> None:
    result = control_request("POST", "/intake/heartbeat", claim)
    if result.get("renewed") is not True:
        raise RuntimeError("planner heartbeat was not renewed")


def publish_new(args):
    paths = changed_files()
    heartbeat(args.claim)
    sha, base_ref = create_plan_commit(paths, args.issue)
    branch = f"agent/codex/issue-{args.issue}"
    body = body_for(args.issue)
    prepare = {
        **args.claim,
        "head_ref": branch,
        "head_sha": sha,
        "base_ref": base_ref,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
    }
    receipt = control_request("POST", "/intake/prepare-publication", prepare)
    publication_id = str(receipt["publication_id"])
    heartbeat(args.claim)
    ensure_branch(branch, sha)
    heartbeat(args.claim)
    pr_number = ensure_pr(args.issue, branch, base_ref, sha)
    ensure_handoff(pr_number, args.issue, branch, sha, paths)
    confirmed = control_request(
        "POST",
        "/intake/confirm-publication",
        {**args.claim, "publication_id": publication_id, "pr_number": pr_number},
    )
    if confirmed.get("status") != "applied":
        raise RuntimeError("planner publication confirmation failed")
    return {"status": "confirmed", "pr_number": pr_number, "source_sha": sha}


def publish_resume(args):
    request = {**args.claim, "publication_id": args.publication_id}
    receipt = control_request("POST", "/intake/resume-publication", request)
    intent = receipt["intent"]
    if int(intent["issue_number"]) != args.issue:
        raise RuntimeError("publication belongs to another issue")
    body = body_for(args.issue)
    if hashlib.sha256(body.encode()).hexdigest() != intent["body_sha256"]:
        raise RuntimeError("resumed PR body no longer matches immutable intent")
    heartbeat(args.claim)
    ensure_branch(intent["head_ref"], intent["head_sha"])
    heartbeat(args.claim)
    pr_number = ensure_pr(
        args.issue, intent["head_ref"], intent["base_ref"], intent["head_sha"]
    )
    artifacts = commit_artifacts(intent["head_sha"])
    ensure_handoff(
        pr_number, args.issue, intent["head_ref"], intent["head_sha"], artifacts
    )
    confirmed = control_request(
        "POST",
        "/intake/confirm-publication",
        {**request, "pr_number": pr_number},
    )
    if confirmed.get("status") != "applied":
        raise RuntimeError("resumed publication confirmation failed")
    return {
        "status": "confirmed",
        "pr_number": pr_number,
        "source_sha": intent["head_sha"],
    }


class Args:
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["new", "resume"], required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--lease-id", required=True)
    parser.add_argument("--publication-id", default="")
    ns = parser.parse_args()
    args = Args()
    args.issue = ns.issue
    args.publication_id = ns.publication_id
    args.claim = {
        "issue_number": ns.issue,
        "generation": ns.generation,
        "worker_id": ns.worker_id,
        "lease_id": ns.lease_id,
    }
    if ns.mode == "new":
        result = publish_new(args)
    else:
        if not ns.publication_id:
            raise SystemExit("--publication-id is required for resume")
        result = publish_resume(args)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
