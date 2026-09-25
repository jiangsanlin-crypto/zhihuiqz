"""Recover a Work review repair without treating the repair as a review PASS."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.reconcile_handoff_state import _labels, _successful_current_ci

MERGE_CONFLICT_GRACE = timedelta(minutes=20)
MISSING_CI_GRACE = timedelta(minutes=60)
BLOCKER_LABEL = "recovery:repair-ci"


def timestamp(raw: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def decide_repair_recovery(
    pr: dict[str, Any], comments: list[dict[str, Any]],
    ci_runs: dict[str, Any], *, now: datetime, owner: str,
) -> dict[str, Any]:
    labels = _labels(pr)
    head = pr.get("head") or {}
    sha = str(head.get("sha") or "")
    if (pr.get("state") != "open" or pr.get("merged_at") or not sha
        or {label for label in labels if label.startswith("agent:")} != {"agent:workreview"}
        or {label for label in labels if label.startswith("phase:")} != {"phase:escalation-repair"}
        or {label for label in labels if label.startswith("status:")} not in (
            {"status:todo"}, {"status:running"}, {"status:blocked"}
        ) or labels & {"status:review", "approval:production-required"}):
        return {"action": "noop", "reason": "not_repair_waiting_for_ci"}

    blocked = "status:blocked" in labels
    legacy_blocked = blocked and BLOCKER_LABEL not in labels
    if legacy_blocked and any(label.startswith("blocker:") or label == "watchdog:timeout"
                              for label in labels):
        return {"action": "noop", "reason": "unrelated_blocker"}

    # An owner-authored repair or recovery observation binds the waiting phase
    # to the current commit. It is never an independent review PASS.
    repair_at: datetime | None = None
    for comment in comments:
        user = comment.get("user") or {}
        if isinstance(user, str):
            user = {"login": user}
        if user.get("login") != owner:
            continue
        body = str(comment.get("body") or "")
        if not any(marker in body for marker in (
            "<!-- agent-repair:v1 -->", "<!-- agent-resume:v1 -->",
            "<!-- repair-ci-wait:v1 -->",
        )) or "phase=escalation-repair" not in body or not any(
            marker in body for marker in (
                "status=waiting_ci", "status=waiting_exact_sha_ci"
            )
        ):
            continue
        if legacy_blocked and not (
            "<!-- repair-ci-wait:v1 -->" in body
            and "blocker_code=REVIEW_REPAIR_MERGE_CONFLICT" in body
            and "source_sha=" in body
        ):
            continue
        if f"source_sha={sha}" not in body and not blocked:
            continue
        when = timestamp(comment.get("created_at"))
        if when and (repair_at is None or when > repair_at):
            repair_at = when
    if repair_at is None:
        return {"action": "noop", "reason": (
            "unrelated_blocker" if legacy_blocked else "missing_trusted_repair_record"
        )}

    ci_id = _successful_current_ci(
        ci_runs, head_sha=sha, head_ref=str(head.get("ref") or "")
    )
    if ci_id is not None and pr.get("mergeable_state") != "dirty":
        return {
            "action": "requeue_review", "rule_id": "R06_REPAIR_CI_RECOVERED",
            "source_sha": sha, "ci_run_id": ci_id,
            "labels_before": sorted(labels),
            "labels_after": sorted((labels - {
                "status:todo", "status:running", "status:blocked",
                "phase:escalation-repair", BLOCKER_LABEL,
            }) | {"status:todo", "phase:code-review"}),
        }

    if not blocked and now - repair_at < (
        MERGE_CONFLICT_GRACE if pr.get("mergeable_state") == "dirty"
        else MISSING_CI_GRACE
    ):
        return {"action": "noop", "reason": "awaiting_current_sha_ci"}

    runs = [run for run in ci_runs.get("workflow_runs", [])
            if isinstance(run, dict) and run.get("head_sha") == sha
            and run.get("event") == "pull_request"
            and run.get("path") == ".github/workflows/ci.yml"]
    if pr.get("mergeable_state") == "dirty":
        reason = "REVIEW_REPAIR_MERGE_CONFLICT"
    elif any(run.get("status") == "completed" for run in runs):
        reason = "REVIEW_REPAIR_CI_FAILED"
    else:
        reason = "REVIEW_REPAIR_CI_MISSING"

    if blocked:
        return {"action": "noop", "reason": reason}
    return {
        "action": "block", "rule_id": "R05_REPAIR_CI_BLOCKER", "reason": reason,
        "source_sha": sha, "labels_before": sorted(labels),
        "labels_after": sorted((labels - {"status:todo", "status:running"}) | {
            "status:blocked", BLOCKER_LABEL,
        }),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for arg in ("pr-json", "comments-json", "ci-runs-json", "repository-owner", "now"):
        parser.add_argument(f"--{arg}", required=True)
    args = parser.parse_args()
    decision = decide_repair_recovery(
        json.loads(Path(args.pr_json).read_text()),
        json.loads(Path(args.comments_json).read_text()),
        json.loads(Path(args.ci_runs_json).read_text()),
        now=timestamp(args.now) or (_ for _ in ()).throw(ValueError("invalid now")),
        owner=args.repository_owner,
    )
    print(json.dumps(decision, sort_keys=True))


if __name__ == "__main__":
    main()
