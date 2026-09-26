"""Shared, side-effect-free evidence gates for workers and reconciliation."""

from __future__ import annotations

from typing import Any

from .handoff_gate import (
    HandoffGateError, extract_handoff, independent_review_pass, validate_handoff,
)


def successful_current_ci(
    ci_runs: dict[str, Any], *, head_sha: str, head_ref: str
) -> int | None:
    runs = ci_runs.get("workflow_runs")
    if not isinstance(runs, list) or not head_sha or not head_ref:
        return None
    candidates = [run for run in runs if isinstance(run, dict)
                  and run.get("head_sha") == head_sha
                  and run.get("head_branch") == head_ref
                  and run.get("event") == "pull_request"
                  and run.get("path") == ".github/workflows/ci.yml"
                  and run.get("name") == "CI"]
    if not candidates:
        return None
    latest = max(candidates, key=lambda run: (
        str(run.get("created_at") or ""), int(run.get("id") or 0)
    ))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        return None
    return int(latest["id"])


def validate_qa_evidence(
    comments: list[dict[str, Any]], ci_runs: dict[str, Any], *,
    task_id: str, head_sha: str, head_ref: str, trusted_login: str,
    pr_number: int,
) -> dict[str, Any]:
    """QA needs both ordinary CI and a fresh independent account review."""
    payload = validate_handoff(
        comments, task_id=task_id, from_agent="workreview",
        to_agent="workbuddy", phase="code_review", source_sha=head_sha,
        trusted_logins={trusted_login},
    )
    if payload.get("pr_number") not in (None, pr_number):
        raise HandoffGateError("review belongs to another PR")
    matches = []
    for comment in comments:
        if (comment.get("user") or {}).get("login") != trusted_login:
            continue
        try:
            candidate = extract_handoff(str(comment.get("body") or ""))
        except HandoffGateError:
            continue
        if candidate == payload:
            matches.append(comment)
    if not matches or not independent_review_pass(
        comments, handoff=payload, handoff_comment=max(matches, key=lambda item: (
            str(item.get("created_at") or ""), int(item.get("id") or 0)
        )), task_id=task_id, source_sha=head_sha, trusted_login=trusted_login,
    ):
        raise HandoffGateError("independent current-SHA Work Review PASS missing")
    if successful_current_ci(ci_runs, head_sha=head_sha, head_ref=head_ref) is None:
        raise HandoffGateError("current-SHA ordinary CI has not passed")
    return payload


def owner_wait_evidence(
    comments: list[dict[str, Any]], *, task_id: str, head_sha: str
) -> bool:
    """A label alone cannot authorize cleanup into the human terminal state."""
    terminal: tuple[tuple[str, int], dict[str, str]] | None = None
    qa: tuple[tuple[str, int], dict[str, Any]] | None = None
    for comment in comments:
        if (comment.get("user") or {}).get("login") != "github-actions[bot]":
            continue
        body = str(comment.get("body") or "")
        order = (str(comment.get("created_at") or ""), int(comment.get("id") or 0))
        if "<!-- terminal-policy:v1 -->" in body:
            fields = dict(
                line.split("=", 1) for line in body.splitlines()
                if "=" in line and line.split("=", 1)[0] in {
                    "task_id", "source_sha", "policy", "release_enabled"
                }
            )
            if fields.get("task_id") == task_id and fields.get("source_sha") == head_sha:
                if terminal is None or order > terminal[0]:
                    terminal = (order, fields)
        try:
            payload = extract_handoff(body)
        except Exception:
            continue
        if (payload and payload.get("task_id") == task_id
            and payload.get("source_sha") == head_sha
            and payload.get("from_agent") == "workbuddy"
            and payload.get("phase") in {"qa", "qa_acceptance"}
            and (qa is None or order > qa[0])):
            qa = (order, payload)
    return bool(
        terminal and qa
        and terminal[1].get("policy") in {"owner_approval_required", "stop_after_qa"}
        and terminal[1].get("release_enabled") == "false"
        and qa[1].get("status") == "success"
        and not qa[1].get("blockers")
    )
