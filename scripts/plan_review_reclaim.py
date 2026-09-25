from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from orchestrator.handoff_gate import extract_handoff
from scripts.reconcile_handoff_state import _labels, _successful_current_ci

STALE_AFTER = timedelta(minutes=60)


def _timestamp(raw: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def decide_reclaim(
    pr: dict[str, Any],
    comments: list[dict[str, Any]],
    ci_runs: dict[str, Any],
    *,
    now: datetime,
    owner: str,
) -> dict[str, Any]:
    labels = _labels(pr)
    head = pr.get("head") or {}
    sha = str(head.get("sha") or "")
    if (
        pr.get("state") != "open" or pr.get("merged_at")
        or not sha
        or {x for x in labels if x.startswith("agent:")} != {"agent:workreview"}
        or {x for x in labels if x.startswith("phase:")} != {"phase:code-review"}
        or {x for x in labels if x.startswith("status:")} != {"status:running"}
        or "approval:production-required" in labels
    ):
        return {"action": "noop", "reason": "not_review_running"}
    if _successful_current_ci(
        ci_runs, head_sha=sha, head_ref=str(head.get("ref") or "")
    ) is None:
        return {"action": "noop", "reason": "current_sha_ci_not_success"}

    progress: list[datetime] = []
    for comment in comments:
        if (comment.get("user") or {}).get("login") != owner:
            continue
        body = str(comment.get("body") or "")
        if f"source_sha={sha}" in body and any(
            marker in body for marker in (
                "<!-- agent-claim:v1 -->",
                "<!-- agent-heartbeat:v1 -->",
                "<!-- agent-retry:v1 -->",
                "<!-- agent-repair:v1 -->",
            )
        ):
            when = _timestamp(comment.get("created_at"))
            if when:
                progress.append(when)
        try:
            handoff = extract_handoff(body)
        except Exception:
            handoff = None
        if (
            handoff and handoff.get("source_sha") == sha
            and handoff.get("from_agent") == "workreview"
            and handoff.get("phase") == "code_review"
        ):
            return {"action": "noop", "reason": "review_result_exists"}

    # PR updated_at can include a concurrent comment or label edit. Using the
    # newer clock fails closed when we cannot establish when RUNNING began.
    started = _timestamp(pr.get("updated_at"))
    if started:
        progress.append(started)
    if not progress or now - max(progress) < STALE_AFTER:
        return {"action": "noop", "reason": "review_may_still_be_active"}

    return {
        "action": "requeue",
        "rule_id": "R04_EXPIRED_REVIEW_RUNNING",
        "source_sha": sha,
        "labels_before": sorted(labels),
        "labels_after": sorted((labels - {"status:running"}) | {"status:todo"}),
        "last_progress_at": max(progress).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-json", required=True)
    parser.add_argument("--comments-json", required=True)
    parser.add_argument("--ci-runs-json", required=True)
    parser.add_argument("--repository-owner", required=True)
    parser.add_argument("--now", required=True)
    args = parser.parse_args()
    decision = decide_reclaim(
        json.loads(Path(args.pr_json).read_text()),
        json.loads(Path(args.comments_json).read_text()),
        json.loads(Path(args.ci_runs_json).read_text()),
        now=_timestamp(args.now) or (_ for _ in ()).throw(ValueError("invalid now")),
        owner=args.repository_owner,
    )
    print(json.dumps(decision, sort_keys=True))


if __name__ == "__main__":
    main()
