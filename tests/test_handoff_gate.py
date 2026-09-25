import json

import pytest

from orchestrator.handoff_gate import (
    HandoffGateError, independent_review_pass, validate_handoff,
)


def comment(payload, created_at="2026-09-23T01:00:00Z", user="owner"):
    return {
        "created_at": created_at,
        "user": {"login": user},
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


def test_late_stale_sha_handoff_does_not_mask_current_one():
    current = base_payload()
    stale = {**current, "source_sha": "old"}
    result = validate_handoff(
        [comment(current, created_at="2026-09-23T01:00:00Z"),
         comment(stale, created_at="2026-09-23T02:00:00Z")],
        task_id="GH-ISSUE-12", from_agent="workbuddy",
        to_agent="chatgpt", phase="prototype_validation",
        source_sha="abc123", trusted_logins={"owner"},
    )
    assert result["source_sha"] == "abc123"


def test_latest_current_sha_blocker_overrides_earlier_pass():
    current = base_payload()
    blocked = {**current, "status": "blocked", "blockers": ["QA failed"]}
    stale = {**current, "source_sha": "old"}
    with pytest.raises(HandoffGateError, match="handoff status"):
        validate_handoff(
            [comment(current, created_at="2026-09-23T01:00:00Z"),
             comment(blocked, created_at="2026-09-23T02:00:00Z"),
             comment(stale, created_at="2026-09-23T03:00:00Z")],
            task_id="GH-ISSUE-12", from_agent="workbuddy",
            to_agent="chatgpt", phase="prototype_validation",
            source_sha="abc123", trusted_logins={"owner"},
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


def test_untrusted_forged_handoff_is_ignored():
    forged = base_payload()
    trusted = base_payload()
    result = validate_handoff(
        [
            comment(trusted, created_at="2026-09-23T01:00:00Z", user="owner"),
            comment(forged, created_at="2026-09-23T02:00:00Z", user="attacker"),
        ],
        task_id="GH-ISSUE-12",
        from_agent="workbuddy",
        to_agent="chatgpt",
        phase="prototype_validation",
        source_sha="abc123",
        trusted_logins={"owner", "github-actions[bot]"},
    )
    assert result["source_sha"] == "abc123"


def test_untrusted_malformed_handoff_cannot_dos_gate():
    malformed = {
        "created_at": "2026-09-23T02:00:00Z",
        "user": {"login": "attacker"},
        "body": "<!-- agent-handoff:v1 -->\n```json\n{broken\n```",
    }
    result = validate_handoff(
        [
            malformed,
            comment(base_payload(), user="owner"),
        ],
        task_id="GH-ISSUE-12",
        from_agent="workbuddy",
        to_agent="chatgpt",
        phase="prototype_validation",
        source_sha="abc123",
        trusted_logins={"owner", "github-actions[bot]"},
    )
    assert result["status"] == "success"


def test_trusted_malformed_handoff_fails_closed():
    malformed = {
        "created_at": "2026-09-23T02:00:00Z",
        "user": {"login": "owner"},
        "body": "<!-- agent-handoff:v1 -->\n```json\n{broken\n```",
    }
    with pytest.raises(HandoffGateError):
        validate_handoff(
            [malformed],
            task_id="GH-ISSUE-12",
            from_agent="workbuddy",
            to_agent="chatgpt",
            phase="prototype_validation",
            trusted_logins={"owner", "github-actions[bot]"},
        )


def test_independent_review_requires_fresh_claim_and_explicit_pass():
    payload = {
        "task_id": "GH-ISSUE-12", "from_agent": "workreview",
        "to_agent": "workbuddy", "phase": "code_review",
        "status": "success", "source_sha": "review123",
        "checks": [{"name": "code_review", "status": "passed"}],
    }
    claim = {
        "created_at": "2026-09-23T00:00:00Z",
        "user": {"login": "owner"},
        "body": "<!-- agent-claim:v1 -->\ntask_id=GH-ISSUE-12\nagent=workreview\n"
                "phase=code-review\nsource_sha=review123",
    }
    pass_comment = comment(payload, created_at="2026-09-23T02:00:00Z")
    kwargs = dict(handoff=payload, handoff_comment=pass_comment,
                  task_id="GH-ISSUE-12", source_sha="review123", trusted_login="owner")
    assert independent_review_pass([claim, pass_comment], **kwargs)
    live_check = {**payload, "checks": [
        {"name": "independent_code_review", "status": "passed"}
    ]}
    live_pass_comment = comment(
        live_check, created_at="2026-09-23T02:00:00Z"
    )
    assert independent_review_pass(
        [claim, live_pass_comment],
        **{**kwargs, "handoff": live_check,
           "handoff_comment": live_pass_comment},
    )
    requeue = {
        "created_at": "2026-09-23T01:00:00Z",
        "user": {"login": "owner"},
        "body": "<!-- work-review-requeue:v1 -->\ntask_id=GH-ISSUE-12\nsource_sha=review123",
    }
    assert not independent_review_pass([claim, requeue, pass_comment], **kwargs)
    qa_marker = {
        "created_at": "2026-09-23T01:00:00Z",
        "user": {"login": "github-actions[bot]"},
        "body": "<!-- qa-postwrite-review:v1 -->\ntask_id=GH-ISSUE-12\n"
                "source_sha=review123\nnext=NEW_INDEPENDENT_WORK_CODE_REVIEW",
    }
    assert not independent_review_pass(
        [claim, qa_marker, pass_comment], **kwargs
    )
    post_qa_claim = dict(claim, created_at="2026-09-23T01:30:00Z")
    assert independent_review_pass(
        [claim, qa_marker, post_qa_claim, pass_comment], **kwargs
    )
    assert not independent_review_pass(
        [dict(claim, user={"login": "attacker"}), pass_comment], **kwargs
    )
    assert not independent_review_pass([dict(claim, body=claim["body"].replace(
        "review123", "stale123")), pass_comment], **kwargs)
    assert not independent_review_pass(
        [claim, pass_comment], **dict(kwargs, handoff=dict(payload, checks=[]))
    )
