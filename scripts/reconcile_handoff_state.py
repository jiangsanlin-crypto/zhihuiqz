from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from orchestrator.handoff_gate import extract_handoff, independent_review_pass

TASK_ID_RE = re.compile(r"<!-- agent-task-id:([A-Za-z0-9._:-]+) -->")

TRANSITIONS = {
    ("chatgpt", "workreview", "implementation"): ("agent:workreview", "phase:code-review"),
    ("workreview", "workbuddy", "code_review"): ("agent:workbuddy", "phase:qa"),
}

STATE_LABELS = {
    "agent:codex", "agent:chatgpt", "agent:workreview", "agent:workbuddy",
    "phase:product-plan", "phase:prototype", "phase:implementation",
    "phase:code-review", "phase:escalation-repair",
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


def _successful_current_ci(
    ci_runs: dict[str, Any], *, head_sha: str, head_ref: str
) -> int | None:
    """Require the latest ordinary pull-request CI for this exact head to pass."""
    runs = ci_runs.get("workflow_runs")
    if not isinstance(runs, list):
        return None
    candidates = [
        run for run in runs
        if isinstance(run, dict)
        and run.get("head_sha") == head_sha
        and run.get("head_branch") == head_ref
        and run.get("event") == "pull_request"
        and run.get("path") == ".github/workflows/ci.yml"
        and run.get("name") == "CI"
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda run: (str(run.get("created_at") or ""), int(run.get("id") or 0)))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        return None
    return int(latest["id"])


def _owner_wait_evidence(
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


def _post_qa_marker_exists(
    comments: list[dict[str, Any]], *, task_id: str, head_sha: str
) -> bool:
    return any(
        (comment.get("user") or {}).get("login") == "github-actions[bot]"
        and "<!-- qa-postwrite-review:v1 -->" in str(comment.get("body") or "")
        and f"task_id={task_id}" in str(comment.get("body") or "").splitlines()
        and f"source_sha={head_sha}" in str(comment.get("body") or "").splitlines()
        for comment in comments
    )


def decide_reconciliation(
    pr: dict[str, Any],
    comments: list[dict[str, Any]],
    *,
    repository_owner: str,
    ci_runs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if pr.get("state") != "open" or pr.get("merged_at"):
        return {"action": "noop", "reason": "pr_not_open"}

    task_id = _task_id(pr)
    if not task_id:
        return {"action": "noop", "reason": "missing_task_id"}

    head_sha = str((pr.get("head") or {}).get("sha") or "")
    if not head_sha:
        return {"action": "noop", "reason": "missing_head_sha"}

    labels = _labels(pr)
    head_ref = str((pr.get("head") or {}).get("ref") or "")
    ci_run_id = _successful_current_ci(
        ci_runs or {}, head_sha=head_sha, head_ref=head_ref
    )
    # QA artifacts can advance HEAD after the first Work Review. The final
    # owner wait needs a fresh independent review of that final QA commit.
    if ci_run_id and _owner_wait_evidence(
        comments, task_id=task_id, head_sha=head_sha
    ):
        # A later failure on the same SHA revokes an earlier PASS. Select the
        # latest trusted review outcome before considering owner-wait cleanup.
        reviews: list[tuple[tuple[str, int], dict[str, Any], dict[str, Any]]] = []
        for review_comment in comments:
            if (review_comment.get("user") or {}).get("login") != repository_owner:
                continue
            try:
                review = extract_handoff(str(review_comment.get("body") or ""))
            except Exception:
                continue
            if not (review and review.get("task_id") == task_id
                and review.get("source_sha") == head_sha
                and review.get("from_agent") == "workreview"
                and review.get("to_agent") == "workbuddy"
                and review.get("phase") == "code_review"):
                continue
            reviews.append(((str(review_comment.get("created_at") or ""),
                             int(review_comment.get("id") or 0)), review_comment, review))
        if reviews:
            _, review_comment, review = max(reviews, key=lambda item: item[0])
            if (review.get("status") == "success" and not review.get("blockers")
                and independent_review_pass(
                    comments, handoff=review, handoff_comment=review_comment,
                    task_id=task_id, source_sha=head_sha,
                    trusted_login=repository_owner,
                )):
                if labels & {"approval:production-approved", "status:blocked"}:
                    return {"action": "noop", "reason": "owner_wait_has_other_blocker"}
                canonical = (labels - STATE_LABELS) | {
                    "status:review", "approval:production-required"
                }
                if canonical == labels:
                    return {"action": "noop", "reason": "intentional_owner_wait"}
                return {
                    "action": "converge_owner_wait", "source_sha": head_sha,
                    "ci_run_id": ci_run_id, "labels_before": sorted(labels),
                    "labels_after": sorted(canonical),
                }
        qa_running = {"agent:workbuddy", "phase:qa"} <= labels and bool(
            labels & {"status:running", "status:todo"}
        )
        review_queued = {
            "agent:workreview", "phase:code-review", "status:todo"
        } <= labels
        if (qa_running or review_queued) and not labels & {
            "status:blocked", "status:review", "approval:production-required",
            "approval:production-approved",
        }:
            canonical = (labels - STATE_LABELS) | {
                "agent:workreview", "phase:code-review", "status:todo"
            }
            # A complete label projection without its marker is still
            # incomplete: the Work consumer needs trusted QA evidence to
            # claim the independent final-SHA review.
            if canonical != labels or not _post_qa_marker_exists(
                comments, task_id=task_id, head_sha=head_sha
            ):
                return {
                    "action": "requeue_post_qa_review", "task_id": task_id,
                    "source_sha": head_sha, "ci_run_id": ci_run_id,
                    "labels_before": sorted(labels),
                    "labels_after": sorted(canonical),
                    "write_marker": not _post_qa_marker_exists(
                        comments, task_id=task_id, head_sha=head_sha
                    ),
                }
    if "status:review" in labels or "approval:production-required" in labels:
        # Human wait is protected from automatic exit, but missing evidence
        # must remain visible as a distinct unresolved state for operators.
        if ci_run_id is None:
            return {"action": "noop", "reason": "owner_wait_current_sha_ci_not_success"}
        if not _owner_wait_evidence(
            comments, task_id=task_id, head_sha=head_sha
        ):
            return {"action": "noop", "reason": "owner_wait_missing_exact_terminal_evidence"}
        if {"status:review", "approval:production-required"} <= labels and labels & STATE_LABELS:
            return {"action": "noop", "reason": "owner_wait_requires_final_sha_review"}
        return {"action": "noop", "reason": "owner_wait_requires_final_sha_review"}

    relevant: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
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
            relevant.append((str(comment.get("created_at") or ""), comment, payload))

    if not relevant:
        return {"action": "noop", "reason": "no_relevant_owner_handoff"}

    # A delayed replay of an old-SHA handoff must not hide valid evidence for
    # the current HEAD. Among current-SHA handoffs, the latest result still
    # wins so a later failure cannot be overridden by an earlier PASS.
    relevant.sort(
        key=lambda item: (
            str(item[2].get("source_sha") or "") == head_sha,
            item[0],
        ),
        reverse=True,
    )
    handoff_comment, payload = relevant[0][1:]
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
    if key == ("workreview", "workbuddy", "code_review") and not independent_review_pass(
        comments, handoff=payload, handoff_comment=handoff_comment,
        task_id=task_id, source_sha=head_sha, trusted_login=repository_owner,
    ):
        return {"action": "noop", "reason": "missing_independent_current_sha_review_pass"}

    # Only machine timeout blockers may recover from a validated handoff.
    # Policy/content blockers remain under explicit ownership.
    if "status:blocked" in labels and (
        "watchdog:timeout" not in labels
        or "recovery:technical" in labels
        or any(label.startswith("blocker:") for label in labels)
    ):
        return {"action": "noop", "reason": "blocked_requires_recovery"}

    # A success handoff is not a substitute for GitHub's current-head CI.
    # In particular, a Work Review handoff alone must not wake Validator QA.
    ci_run_id = _successful_current_ci(
        ci_runs or {},
        head_sha=head_sha,
        head_ref=str((pr.get("head") or {}).get("ref") or ""),
    )
    if ci_run_id is None:
        return {"action": "noop", "reason": "current_sha_ci_not_success"}

    desired_status = (
        "status:running"
        if {target_agent, target_phase, "status:running"}.issubset(labels)
        else "status:todo"
    )
    if "status:blocked" in labels:
        desired_status = "status:todo"
    canonical = {target_agent, target_phase, desired_status}
    current_state = labels & STATE_LABELS

    if current_state == canonical:
        # A successful label projection is not proof that the downstream
        # dispatch succeeded. Revisit an idle QA handoff on the next scan.
        return {
            "action": "ensure_qa_dispatch" if target_phase == "phase:qa" and desired_status == "status:todo" else "noop",
            "reason": "canonical_qa_may_need_dispatch" if target_phase == "phase:qa" and desired_status == "status:todo" else "already_canonical",
            "task_id": task_id,
            "source_sha": head_sha,
            "target_agent": target_agent,
            "target_phase": target_phase,
            "desired_status": desired_status,
            "ci_run_id": ci_run_id,
            "labels_before": sorted(labels),
        }

    return {
        "action": "reconcile",
        "reason": "validated_timeout_resolved" if "status:blocked" in labels else "valid_handoff_requires_state_convergence",
        "task_id": task_id,
        "source_sha": head_sha,
        "from_agent": key[0],
        "to_agent": key[1],
        "phase": key[2],
        "target_agent": target_agent,
        "target_phase": target_phase,
        "desired_status": desired_status,
        "ci_run_id": ci_run_id,
        "labels_before": sorted(labels),
        "remove_labels": sorted((current_state - canonical) | (
            {"watchdog:timeout"} if "status:blocked" in labels else set()
        )),
        "labels_after": sorted((labels - STATE_LABELS - (
            {"watchdog:timeout"} if "status:blocked" in labels else set()
        )) | canonical),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--repository-owner", required=True)
    parser.add_argument("--ci-runs-json", required=True)
    args = parser.parse_args()

    pr = json.loads(Path(args.pr_json).read_text())
    comments = json.loads(Path(args.comments_json).read_text())
    ci_runs = json.loads(Path(args.ci_runs_json).read_text())
    if not isinstance(pr, dict):
        raise SystemExit("PR JSON must be an object")
    if not isinstance(comments, list):
        raise SystemExit("comments JSON must be an array")
    if not isinstance(ci_runs, dict):
        raise SystemExit("CI runs JSON must be an object")

    decision = decide_reconciliation(
        pr, comments, repository_owner=args.repository_owner, ci_runs=ci_runs
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
