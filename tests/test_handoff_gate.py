import json

import pytest

from orchestrator.handoff_gate import HandoffGateError, validate_handoff


def comment(payload, created_at="2026-09-23T01:00:00Z"):
    return {
        "created_at": created_at,
        "body": (
            "<!-- agent-handoff:v1 -->\n"
            "```json\n"
            + json.dumps(payload)
            + "\n```"
        ),
    }


def base_payload():
    return {
        "version": "1.0",
        "task_id": "GH-ISSUE-12",
        "from_agent": "workbuddy",
        "to_agent": "chatgpt",
        "phase": "prototype_validation",
        "status": "success",
        "summary": "ok",
        "artifacts": [],
        "checks": [],
        "blockers": [],
        "source_sha": "abc123",
    }


def test_valid_handoff_passes():
    payload = base_payload()
    result = validate_handoff(
        [comment(payload)],
        task_id="GH-ISSUE-12",
        from_agent="workbuddy",
        to_agent="chatgpt",
        phase="prototype_validation",
        source_sha="abc123",
    )
    assert result["status"] == "success"


def test_blocked_handoff_fails():
    payload = base_payload()
    payload["status"] = "blocked"
    payload["blockers"] = ["taxonomy mismatch"]

    with pytest.raises(HandoffGateError):
        validate_handoff(
            [comment(payload)],
            task_id="GH-ISSUE-12",
            from_agent="workbuddy",
            to_agent="chatgpt",
            phase="prototype_validation",
            source_sha="abc123",
        )


def test_wrong_sha_fails():
    with pytest.raises(HandoffGateError):
        validate_handoff(
            [comment(base_payload())],
            task_id="GH-ISSUE-12",
            from_agent="workbuddy",
            to_agent="chatgpt",
            phase="prototype_validation",
            source_sha="different",
        )


def test_missing_handoff_fails():
    with pytest.raises(HandoffGateError):
        validate_handoff(
            [],
            task_id="GH-ISSUE-12",
            from_agent="workbuddy",
            to_agent="chatgpt",
            phase="prototype_validation",
        )


def test_valid_work_review_handoff_passes():
    payload = {
        "version": "1.0",
        "task_id": "GH-ISSUE-12",
        "from_agent": "workreview",
        "to_agent": "workbuddy",
        "phase": "code_review",
        "status": "success",
        "summary": "reviewed",
        "artifacts": [],
        "checks": [
            {"name": "code_review", "status": "passed", "detail": "no blockers"}
        ],
        "blockers": [],
        "source_sha": "review123",
    }
    result = validate_handoff(
        [comment(payload)],
        task_id="GH-ISSUE-12",
        from_agent="workreview",
        to_agent="workbuddy",
        phase="code_review",
        source_sha="review123",
    )
    assert result["status"] == "success"
