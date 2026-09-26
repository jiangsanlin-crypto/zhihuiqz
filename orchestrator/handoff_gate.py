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


def independent_review_pass(
    comments: list[dict[str, Any]],
    *,
    handoff: dict[str, Any],
    handoff_comment: dict[str, Any],
    task_id: str,
    source_sha: str,
    trusted_login: str,
) -> bool:
    """Require a fresh exact-SHA review claim and an explicit PASS check.

    A repair/requeue on the same SHA invalidates an earlier claim. A repair
    execution cannot approve its own result by publishing a handoff.
    """
    if not any(
        isinstance(check, dict)
        and check.get("name") in {"code_review", "independent_code_review"}
        and check.get("status") == "passed"
        for check in handoff.get("checks") or []
    ):
        return False
    if _comment_login(handoff_comment) != trusted_login:
        return False

    def order(comment: dict[str, Any]) -> tuple[str, int]:
        return str(comment.get("created_at") or ""), int(comment.get("id") or 0)

    pass_order = order(handoff_comment)
    claims: list[tuple[str, int]] = []
    invalidated: list[tuple[str, int]] = []
    for comment in comments:
        login = _comment_login(comment)
        if login not in {trusted_login, "github-actions[bot]"}:
            continue
        body = str(comment.get("body") or "")
        if f"task_id={task_id}" not in body or f"source_sha={source_sha}" not in body:
            continue
        position = order(comment)
        if (login == "github-actions[bot]"
            and "<!-- qa-postwrite-review:v1 -->" in body):
            invalidated.append(position)
            continue
        if login != trusted_login:
            continue
        if (
            "<!-- agent-claim:v1 -->" in body
            and "agent=workreview" in body
            and "phase=code-review" in body
        ):
            claims.append(position)
        if "<!-- agent-repair:v1 -->" in body or "<!-- work-review-requeue:v1 -->" in body:
            invalidated.append(position)
    if not claims:
        return False
    claim_order = max(claims)
    return claim_order < pass_order and (
        not invalidated or claim_order > max(invalidated)
    )


def latest_matching_handoff(
    comments: list[dict[str, Any]],
    *,
    task_id: str,
    from_agent: str,
    to_agent: str,
    phase: str,
    source_sha: str | None = None,
    trusted_logins: set[str] | None = None,
) -> dict[str, Any]:
    parsed: list[tuple[str, int, dict[str, Any]]] = []

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
        parsed.append((created_at, int(comment.get("id") or 0), payload))

    # An old-SHA handoff delivered late cannot mask an earlier valid
    # current-SHA record. The latest result for the current SHA still wins.
    parsed.sort(
        key=lambda item: (
            source_sha is not None and item[2].get("source_sha") == source_sha,
            item[0],
            item[1],
        ),
        reverse=True,
    )

    for _, _, payload in parsed:
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
        source_sha=source_sha,
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
