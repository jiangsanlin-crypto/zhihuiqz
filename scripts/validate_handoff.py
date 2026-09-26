from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator.handoff_gate import (
    HandoffGateError, extract_handoff, independent_review_pass, validate_handoff,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comments", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--from-agent", required=True)
    parser.add_argument("--to-agent", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--trusted-login", action="append", default=[])
    parser.add_argument("--require-independent-review", action="store_true")
    args = parser.parse_args()

    comments = json.loads(Path(args.comments).read_text())
    if not isinstance(comments, list):
        raise SystemExit("comments file must contain a JSON array")

    try:
        payload = validate_handoff(
            comments,
            task_id=args.task_id,
            from_agent=args.from_agent,
            to_agent=args.to_agent,
            phase=args.phase,
            source_sha=args.source_sha or None,
            trusted_logins=set(args.trusted_login) if args.trusted_login else None,
        )
        if args.require_independent_review:
            matches = []
            for comment in comments:
                if (comment.get("user") or {}).get("login") != args.trusted_login[0]:
                    continue
                try:
                    candidate = extract_handoff(str(comment.get("body") or ""))
                except HandoffGateError:
                    continue
                if candidate == payload:
                    matches.append(comment)
            if not matches or not independent_review_pass(
                comments, handoff=payload, handoff_comment=max(
                    matches, key=lambda item: (str(item.get("created_at") or ""), int(item.get("id") or 0))
                ),
                task_id=args.task_id, source_sha=args.source_sha,
                trusted_login=args.trusted_login[0],
            ):
                raise HandoffGateError("independent current-SHA Work Review PASS missing")
    except HandoffGateError as exc:
        print(f"HANDOFF_GATE=BLOCKED: {exc}")
        return 1

    print(
        "HANDOFF_GATE=PASS "
        f"{payload['from_agent']}/{payload['phase']} -> {payload['to_agent']} "
        f"task={payload['task_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
