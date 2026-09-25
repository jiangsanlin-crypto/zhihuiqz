from __future__ import annotations

import json
import re
from typing import Any

HANDOFF_MARKER = "<!-- agent-handoff:v1 -->"
JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


class HandoffGateError(ValueError):
    pass


def extract_handoff(body: str) -> dict[str, Any] | None:
    if HANDOFF_MARKER not in body:
        return None

    match = JSON_BLOCK.search(body)
    if not match:
        raise HandoffGateError("handoff marker exists but JSON payload is missing")

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise HandoffGateError(f"invalid handoff JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise HandoffGateError("handoff payload is not an object")
    return payload


def _comment_login(comment: dict[str, Any]) -> str:
    user = comment.get("user") or {}
    return str(user.get("login") or "")


def latest_matching_handoff(
    comments: list[dict[str, Any]],
    *,
    task_id: str,
    from_agent: str,
    to_agent: str,
    phase: str,
    trusted_logins: set[str] | None = None,
) -> dict[str, Any]:
    parsed: list[tuple[str, dict[str, Any]]] = []

    for comment in comments:
        # Trust is established before parsing. This prevents an untrusted public
        # comment from either forging a handoff or causing a malformed-marker DoS.
        if trusted_logins is not None and _comment_login(comment) not in trusted_logins:
            continue

        body = str(comment.get("body") or "")
        payload = extract_handoff(body)
        if payload is None:
            continue
        created_at = str(comment.get("created_at") or "")
        parsed.append((created_at, payload))

    parsed.sort(key=lambda item: item[0], reverse=True)

    for _, payload in parsed:
        if (
            payload.get("task_id") == task_id
            and payload.get("from_agent") == from_agent
            and payload.get("to_agent") == to_agent
            and payload.get("phase") == phase
        ):
            return payload

    raise HandoffGateError(
        "required successful handoff was not found: "
        f"{from_agent}/{phase} -> {to_agent} for {task_id}"
    )


def validate_handoff(
    comments: list[dict[str, Any]],
    *,
    task_id: str,
    from_agent: str,
    to_agent: str,
    phase: str,
    source_sha: str | None = None,
    trusted_logins: set[str] | None = None,
) -> dict[str, Any]:
    payload = latest_matching_handoff(
        comments,
        task_id=task_id,
        from_agent=from_agent,
        to_agent=to_agent,
        phase=phase,
        trusted_logins=trusted_logins,
    )

    if payload.get("status") != "success":
        raise HandoffGateError(
            f"handoff status is {payload.get('status')!r}, not success"
        )

    blockers = payload.get("blockers") or []
    if blockers:
        raise HandoffGateError(
            "handoff contains blockers: " + "; ".join(map(str, blockers))
        )

    if source_sha and payload.get("source_sha") != source_sha:
        raise HandoffGateError(
            "handoff source SHA does not match the PR head: "
            f"handoff={payload.get('source_sha')} pr={source_sha}"
        )

    return payload
