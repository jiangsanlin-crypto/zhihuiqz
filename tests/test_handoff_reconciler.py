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
        "head": {"sha": sha, "ref": "feature"},
        "labels": [{"name": label} for label in labels],
    }


def ci(sha="abc123", *, conclusion="success", status="completed", event="pull_request"):
    return {"workflow_runs": [{
        "id": 101, "name": "CI", "path": ".github/workflows/ci.yml",
        "event": event, "head_sha": sha, "head_branch": "feature",
        "status": status, "conclusion": conclusion,
        "created_at": "2026-09-25T00:00:00Z",
    }]}


def comment(payload, *, created_at="2026-09-24T00:00:00Z", user=OWNER):
    return {
        "created_at": created_at,
        "user": {"login": user},
        "body": "<!-- agent-handoff:v1 -->\n```json\n"
        + json.dumps(payload)
        + "\n```",
    }


def review_claim(sha="abc123", *, created_at="2026-09-23T00:00:00Z", user=OWNER):
    return {
        "created_at": created_at, "user": {"login": user},
        "body": "<!-- agent-claim:v1 -->\ntask_id=GH-ISSUE-1\n"
                f"agent=workreview\nphase=code-review\nsource_sha={sha}",
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
        "checks": [{"name": "code_review", "status": "passed"}]
        if from_agent == "workreview" and status == "success" else [],
        "source_sha": sha,
        "pr_number": 9,
    }


def test_recovers_partial_chatgpt_to_workreview_transition():
    decision = decide_reconciliation(
        pr(["agent:chatgpt", "phase:implementation", "agent:workreview"]),
        [comment(handoff())],
        repository_owner=OWNER,
        ci_runs=ci(),
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
        ci_runs=ci(),
    )

    assert decision["action"] == "reconcile"
    assert decision["desired_status"] == "status:running"


def test_code_review_handoff_targets_luna_qa():
    decision = decide_reconciliation(
        pr(["agent:workreview", "phase:code-review", "status:running"]),
        [review_claim(),
            comment(
                handoff(
                    from_agent="workreview",
                    to_agent="workbuddy",
                    phase="code_review",
                )
            )
        ],
        repository_owner=OWNER,
        ci_runs=ci(),
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
        ci_runs=ci("new"),
    )

    assert decision == {"action": "noop", "reason": "source_sha_mismatch"}


def test_non_owner_handoff_is_ignored():
    decision = decide_reconciliation(
        pr(["agent:chatgpt", "phase:implementation", "status:running"]),
        [comment(handoff(), user="someone-else")],
        repository_owner=OWNER,
        ci_runs=ci(),
    )

    assert decision == {"action": "noop", "reason": "no_relevant_owner_handoff"}


def test_blocked_handoff_never_advances():
    decision = decide_reconciliation(
        pr(["agent:chatgpt", "phase:implementation", "status:running"]),
        [comment(handoff(blockers=["needs clarification"]))],
        repository_owner=OWNER,
        ci_runs=ci(),
    )

    assert decision == {"action": "noop", "reason": "handoff_has_blockers"}


def test_owner_wait_is_never_requeued_by_old_handoff():
    decision = decide_reconciliation(
        pr(["status:review", "approval:production-required"]),
        [comment(handoff())],
        repository_owner=OWNER,
        ci_runs=ci(),
    )

    assert decision == {"action": "noop", "reason": "intentional_owner_wait"}


def test_blocked_review_is_never_resurrected_by_old_handoff():
    decision = decide_reconciliation(
        pr(["agent:workreview", "phase:code-review", "status:blocked"]),
        [comment(handoff())],
        repository_owner=OWNER,
        ci_runs=ci(),
    )

    assert decision == {"action": "noop", "reason": "blocked_requires_recovery"}


def test_successful_handoff_cannot_advance_qa_without_current_sha_ci():
    payload = handoff(from_agent="workreview", to_agent="workbuddy", phase="code_review")
    state = pr(["agent:workreview", "phase:code-review", "status:running"])
    for evidence in ({"workflow_runs": []}, ci("old"), ci(conclusion="failure"),
                     ci(status="in_progress", conclusion=None), ci(event="push")):
        decision = decide_reconciliation(
            state, [review_claim(), comment(payload)], repository_owner=OWNER, ci_runs=evidence
        )
        assert decision == {"action": "noop", "reason": "current_sha_ci_not_success"}


def test_latest_failed_ci_overrides_older_success_for_same_sha():
    runs = ci()
    failed = dict(runs["workflow_runs"][0], id=102, conclusion="failure",
                  created_at="2026-09-25T00:05:00Z")
    runs["workflow_runs"].append(failed)
    decision = decide_reconciliation(
        pr(["agent:workreview", "phase:code-review", "status:running"]),
        [review_claim(), comment(handoff(from_agent="workreview", to_agent="workbuddy", phase="code_review"))],
        repository_owner=OWNER, ci_runs=runs,
    )
    assert decision == {"action": "noop", "reason": "current_sha_ci_not_success"}


def test_reconcile_projects_one_legal_state_preserving_other_labels():
    decision = decide_reconciliation(
        pr(["agent:workreview", "phase:escalation-repair", "phase:code-review",
            "status:todo", "status:running", "priority:high"]),
        [comment(handoff())], repository_owner=OWNER, ci_runs=ci(),
    )
    assert decision["action"] == "reconcile"
    assert decision["labels_after"] == [
        "agent:workreview", "phase:code-review", "priority:high", "status:running"
    ]
    assert "phase:escalation-repair" in decision["remove_labels"]


def test_canonical_qa_todo_retries_missing_dispatch():
    decision = decide_reconciliation(
        pr(["agent:workbuddy", "phase:qa", "status:todo"]),
        [review_claim(), comment(handoff(from_agent="workreview", to_agent="workbuddy", phase="code_review"))],
        repository_owner=OWNER, ci_runs=ci(),
    )
    assert decision["action"] == "ensure_qa_dispatch"
    assert decision["task_id"] == "GH-ISSUE-1"
    assert decision["labels_before"] == ["agent:workbuddy", "phase:qa", "status:todo"]


def test_running_qa_is_not_redispatched():
    decision = decide_reconciliation(
        pr(["agent:workbuddy", "phase:qa", "status:running"]),
        [review_claim(), comment(handoff(from_agent="workreview", to_agent="workbuddy", phase="code_review"))],
        repository_owner=OWNER, ci_runs=ci(),
    )
    assert decision["action"] == "noop"


def test_review_pass_without_fresh_claim_never_starts_qa():
    payload = handoff(from_agent="workreview", to_agent="workbuddy", phase="code_review")
    state = pr(["agent:workreview", "phase:code-review", "status:running"])
    for prior in ([], [review_claim("old")],
                  [review_claim(), {"user": {"login": OWNER},
                                    "created_at": "2026-09-23T12:00:00Z",
                                    "body": "<!-- work-review-requeue:v1 -->\ntask_id=GH-ISSUE-1\nsource_sha=abc123"}]):
        decision = decide_reconciliation(
            state, prior + [comment(payload)], repository_owner=OWNER, ci_runs=ci()
        )
        assert decision == {"action": "noop", "reason": "missing_independent_current_sha_review_pass"}


def test_review_pass_without_pass_check_never_starts_qa():
    payload = handoff(from_agent="workreview", to_agent="workbuddy", phase="code_review")
    payload["checks"] = []
    decision = decide_reconciliation(
        pr(["agent:workreview", "phase:code-review", "status:running"]),
        [review_claim(), comment(payload)], repository_owner=OWNER, ci_runs=ci()
    )
    assert decision == {"action": "noop", "reason": "missing_independent_current_sha_review_pass"}
