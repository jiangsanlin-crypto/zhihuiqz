from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator.handoff_gate import HandoffGateError, validate_handoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comments", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--from-agent", required=True)
    parser.add_argument("--to-agent", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--source-sha", default="")
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
        )
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
