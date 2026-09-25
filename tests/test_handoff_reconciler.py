from __future__ import annotations

import json

from scripts.reconcile_handoff_state import decide_reconciliation


OWNER = "owner"


def pr(labels, *, sha="abc123", task_id="GH-ISSUE-1"):
    return {
        "number": 9,
        "state": "open",
        "merged_at": None,
        "body": f"<!-- agent-task-id:{task_id} -->",
        "head": {"sha": sha},
        "labels": [{"name": label} for label in labels],
    }


def comment(payload, *, created_at="2026-09-24T00:00:00Z", user=OWNER):
    return {
        "created_at": created_at,
        "user": {"login": user},
        "body": "<!-- agent-handoff:v1 -->\n```json\n"
        + json.dumps(payload)
        + "\n```",
    }


def handoff(
    *,
    from_agent="chatgpt",
    to_agent="workreview",
    phase="implementation",
    sha="abc123",
    task_id="GH-ISSUE-1",
    status="success",
    blockers=None,
):
    return {
        "version": "1.0",
        "task_id": task_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "phase": phase,
        "status": status,
        "blockers": blockers or [],
        "source_sha": sha,
        "pr_number": 9,
    }


def test_recovers_partial_chatgpt_to_workreview_transition():
    decision = decide_reconciliation(
        pr(["agent:chatgpt", "phase:implementation", "agent:workreview"]),
        [comment(handoff())],
        repository_owner=OWNER,
    )

    assert decision["action"] == "reconcile"
    assert decision["target_agent"] == "agent:workreview"
    assert decision["target_phase"] == "phase:code-review"
    assert decision["desired_status"] == "status:todo"
    assert "agent:chatgpt" in decision["remove_labels"]


def test_preserves_running_target_instead_of_requeueing():
    decision = decide_reconciliation(
        pr(
            [
                "agent:chatgpt",
                "agent:workreview",
                "phase:implementation",
                "phase:code-review",
                "status:running",
            ]
        ),
        [comment(handoff())],
        repository_owner=OWNER,
    )

    assert decision["action"] == "reconcile"
    assert decision["desired_status"] == "status:running"


def test_code_review_handoff_targets_luna_qa():
    decision = decide_reconciliation(
        pr(["agent:workreview", "phase:code-review", "status:running"]),
        [
            comment(
                handoff(
                    from_agent="workreview",
                    to_agent="workbuddy",
                    phase="code_review",
                )
            )
        ],
        repository_owner=OWNER,
    )

    assert decision["action"] == "reconcile"
    assert decision["target_agent"] == "agent:workbuddy"
    assert decision["target_phase"] == "phase:qa"
    assert decision["desired_status"] == "status:todo"


def test_exact_sha_mismatch_never_advances():
    decision = decide_reconciliation(
        pr(["agent:chatgpt", "phase:implementation", "status:running"], sha="new"),
        [comment(handoff(sha="old"))],
        repository_owner=OWNER,
    )

    assert decision == {"action": "noop", "reason": "source_sha_mismatch"}


def test_non_owner_handoff_is_ignored():
    decision = decide_reconciliation(
        pr(["agent:chatgpt", "phase:implementation", "status:running"]),
        [comment(handoff(), user="someone-else")],
        repository_owner=OWNER,
    )

    assert decision == {"action": "noop", "reason": "no_relevant_owner_handoff"}


def test_blocked_handoff_never_advances():
    decision = decide_reconciliation(
        pr(["agent:chatgpt", "phase:implementation", "status:running"]),
        [comment(handoff(blockers=["needs clarification"]))],
        repository_owner=OWNER,
    )

    assert decision == {"action": "noop", "reason": "handoff_has_blockers"}


def test_owner_wait_is_never_requeued_by_old_handoff():
    decision = decide_reconciliation(
        pr(["status:review", "approval:production-required"]),
        [comment(handoff())],
        repository_owner=OWNER,
    )

    assert decision == {"action": "noop", "reason": "intentional_owner_wait"}


def test_blocked_review_is_never_resurrected_by_old_handoff():
    decision = decide_reconciliation(
        pr(["agent:workreview", "phase:code-review", "status:blocked"]),
        [comment(handoff())],
        repository_owner=OWNER,
    )

    assert decision == {"action": "noop", "reason": "blocked_requires_recovery"}
