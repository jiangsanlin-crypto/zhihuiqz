from __future__ import annotations

from orchestrator import main
from orchestrator.models import Handoff


def handoff() -> Handoff:
    return Handoff(
        task_id="GH-ISSUE-77",
        from_agent="workbuddy",
        to_agent="human",
        phase="qa_acceptance",
        status="success",
        summary="done",
        source_sha="abc123",
        blockers=[],
    )


def comment(body: str, login: str = "owner") -> dict:
    return {"body": body, "user": {"login": login}}


def test_handoff_comment_is_deduplicated_only_for_exact_trusted_payload():
    value = handoff()
    body = main.handoff_comment(value)
    assert main.handoff_comment_exists([comment(body)], value, "owner/repo")
    assert not main.handoff_comment_exists(
        [comment(body, "untrusted-user")],
        value,
        "owner/repo",
    )

    changed = value.model_copy(update={"source_sha": "new456"})
    assert not main.handoff_comment_exists(
        [comment(body)],
        changed,
        "owner/repo",
    )


def test_terminal_policy_comment_is_deduplicated_by_task_and_sha():
    body = (
        "<!-- terminal-policy:v1 -->\n"
        "task_id=GH-ISSUE-77\n"
        "source_sha=abc123\n"
        "policy=owner_approval_required\n"
        "release_enabled=false"
    )
    comments = [comment(body)]
    assert main.terminal_policy_comment_exists(
        comments,
        "owner/repo",
        "GH-ISSUE-77",
        "abc123",
        "owner_approval_required",
        False,
    )
    assert not main.terminal_policy_comment_exists(
        comments,
        "owner/repo",
        "GH-ISSUE-77",
        "new456",
        "owner_approval_required",
        False,
    )
    assert not main.terminal_policy_comment_exists(
        comments, "owner/repo", "GH-ISSUE-77", "abc123",
        "release_enabled", True,
    )


def test_repository_dispatch_uses_stable_payload_idempotency_key():
    payload = {
        "action": "agent_workbuddy_qa",
        "client_payload": {
            "dispatch_key": "delivery:event:abc123",
        }
    }
    assert main.dispatch_delivery_id(
        payload, "github-delivery-a", "repository_dispatch"
    ) == (
        "repository-dispatch:delivery:event:abc123"
    )
    assert main.dispatch_delivery_id(
        payload, "github-delivery-b", "repository_dispatch"
    ) == (
        "repository-dispatch:delivery:event:abc123"
    )


def test_non_dispatch_event_keeps_github_delivery_id():
    payload = {"action": "opened", "client_payload": {"dispatch_key": "ignored"}}
    assert main.dispatch_delivery_id(
        payload, "github-delivery", "pull_request"
    ) == (
        "github-delivery"
    )
