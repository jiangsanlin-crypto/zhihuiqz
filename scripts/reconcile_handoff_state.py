from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from orchestrator.handoff_gate import extract_handoff

TASK_ID_RE = re.compile(r"<!-- agent-task-id:([A-Za-z0-9._:-]+) -->")

TRANSITIONS = {
    ("chatgpt", "workreview", "implementation"): ("agent:workreview", "phase:code-review"),
    ("workreview", "workbuddy", "code_review"): ("agent:workbuddy", "phase:qa"),
}

STATE_LABELS = {
    "agent:codex", "agent:chatgpt", "agent:workreview", "agent:workbuddy",
    "phase:prototype", "phase:implementation", "phase:code-review",
    "phase:qa", "phase:release", "phase:deploy",
    "status:todo", "status:running", "status:blocked",
}


def _labels(pr: dict[str, Any]) -> set[str]:
    values = pr.get("labels") or []
    labels: set[str] = set()
    for value in values:
        name = value.get("name") if isinstance(value, dict) else value
        if name:
            labels.add(str(name))
    return labels


def _task_id(pr: dict[str, Any]) -> str:
    match = TASK_ID_RE.search(str(pr.get("body") or ""))
    return match.group(1) if match else ""


def decide_reconciliation(
    pr: dict[str, Any],
    comments: list[dict[str, Any]],
    *,
    repository_owner: str,
) -> dict[str, Any]:
    if pr.get("state") != "open" or pr.get("merged_at"):
        return {"action": "noop", "reason": "pr_not_open"}

    task_id = _task_id(pr)
    if not task_id:
        return {"action": "noop", "reason": "missing_task_id"}

    head_sha = str((pr.get("head") or {}).get("sha") or "")
    if not head_sha:
        return {"action": "noop", "reason": "missing_head_sha"}

    relevant: list[tuple[str, dict[str, Any]]] = []
    for comment in comments:
        user = comment.get("user") or {}
        if str(user.get("login") or "") != repository_owner:
            continue
        try:
            payload = extract_handoff(str(comment.get("body") or ""))
        except Exception:
            continue
        if not payload:
            continue
        key = (
            str(payload.get("from_agent") or ""),
            str(payload.get("to_agent") or ""),
            str(payload.get("phase") or ""),
        )
        if key in TRANSITIONS:
            relevant.append((str(comment.get("created_at") or ""), payload))

    if not relevant:
        return {"action": "noop", "reason": "no_relevant_owner_handoff"}

    relevant.sort(key=lambda item: item[0], reverse=True)
    payload = relevant[0][1]
    key = (
        str(payload.get("from_agent") or ""),
        str(payload.get("to_agent") or ""),
        str(payload.get("phase") or ""),
    )
    target_agent, target_phase = TRANSITIONS[key]

    if payload.get("task_id") != task_id:
        return {"action": "noop", "reason": "task_id_mismatch"}
    if payload.get("status") != "success":
        return {"action": "noop", "reason": "handoff_not_success"}
    if payload.get("blockers"):
        return {"action": "noop", "reason": "handoff_has_blockers"}
    if str(payload.get("source_sha") or "") != head_sha:
        return {"action": "noop", "reason": "source_sha_mismatch"}
    if payload.get("pr_number") not in (None, pr.get("number")):
        return {"action": "noop", "reason": "pr_number_mismatch"}

    labels = _labels(pr)
    # Fail closed for terminal/manual states. A previously valid handoff must not
    # resurrect a PR after a later review blocked it or QA moved it to owner wait.
    if "status:review" in labels or "approval:production-required" in labels:
        return {"action": "noop", "reason": "intentional_owner_wait"}
    if "status:blocked" in labels:
        return {"action": "noop", "reason": "blocked_requires_recovery"}

    desired_status = (
        "status:running"
        if {target_agent, target_phase, "status:running"}.issubset(labels)
        else "status:todo"
    )
    canonical = {target_agent, target_phase, desired_status}
    current_state = labels & STATE_LABELS

    if current_state == canonical:
        return {
            "action": "noop",
            "reason": "already_canonical",
            "source_sha": head_sha,
            "target_agent": target_agent,
            "target_phase": target_phase,
            "desired_status": desired_status,
        }

    return {
        "action": "reconcile",
        "reason": "valid_handoff_requires_state_convergence",
        "task_id": task_id,
        "source_sha": head_sha,
        "from_agent": key[0],
        "to_agent": key[1],
        "phase": key[2],
        "target_agent": target_agent,
        "target_phase": target_phase,
        "desired_status": desired_status,
        "remove_labels": sorted(current_state - canonical),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--repository-owner", required=True)
    args = parser.parse_args()

    pr = json.loads(Path(args.pr_json).read_text())
    comments = json.loads(Path(args.comments_json).read_text())
    if not isinstance(pr, dict):
        raise SystemExit("PR JSON must be an object")
    if not isinstance(comments, list):
        raise SystemExit("comments JSON must be an array")

    decision = decide_reconciliation(
        pr, comments, repository_owner=args.repository_owner
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
