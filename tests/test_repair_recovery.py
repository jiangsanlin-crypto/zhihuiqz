from datetime import datetime, timezone

from scripts.plan_repair_recovery import decide_repair_recovery


SHA = "sha-after-repair"
NOW = datetime(2026, 9, 25, 14, 30, tzinfo=timezone.utc)


def pr(*, sha=SHA, status="running", mergeable="dirty"):
    return {
        "state": "open", "merged_at": None, "mergeable_state": mergeable,
        "head": {"sha": sha, "ref": "feature"},
        "labels": [{"name": x} for x in (
            "agent:workreview", "phase:escalation-repair", f"status:{status}",
            *(["recovery:repair-ci"] if status == "blocked" else []),
        )],
    }


def repair(*, sha=SHA, user="owner"):
    return {"user": {"login": user}, "created_at": "2026-09-25T13:25:00Z",
            "body": "<!-- agent-repair:v1 -->\nphase=escalation-repair\n"
                    f"source_sha={sha}\nstatus=waiting_ci"}


def ci(*, sha=SHA, conclusion="success"):
    return {"workflow_runs": [{
        "id": 99, "head_sha": sha, "head_branch": "feature",
        "event": "pull_request", "name": "CI",
        "path": ".github/workflows/ci.yml", "status": "completed",
        "conclusion": conclusion,
    }]}


def decide(state, comments=None, runs=None):
    return decide_repair_recovery(state, comments if comments is not None else [repair()],
                                  runs if runs is not None else {"workflow_runs": []},
                                  now=NOW, owner="owner")


def test_merge_conflict_is_a_recoverable_machine_blocker():
    for status in ("todo", "running"):
        outcome = decide(pr(status=status))
        assert outcome["action"] == "block"
        assert outcome["reason"] == "REVIEW_REPAIR_MERGE_CONFLICT"
        assert "status:blocked" in outcome["labels_after"]
        assert "phase:escalation-repair" in outcome["labels_after"]
    assert decide(pr(status="blocked"))["action"] == "noop"


def test_current_sha_ci_requeues_independent_review_after_repair():
    for status in ("todo", "running", "blocked"):
        result = decide(pr(status=status, mergeable="clean"), runs=ci())
        assert result["action"] == "requeue_review"
        assert result["ci_run_id"] == 99
        assert result["labels_after"] == [
            "agent:workreview", "phase:code-review", "status:todo"
        ]
    assert decide(pr(), runs=ci(sha="old"))["reason"] == "REVIEW_REPAIR_MERGE_CONFLICT"
    assert decide(pr(status="blocked", sha="new", mergeable="clean"), [repair()], ci(sha="new"))["action"] == "requeue_review"
    assert decide(pr(), runs=ci())["reason"] == "REVIEW_REPAIR_MERGE_CONFLICT"


def test_ci_failure_blocks_and_pending_ci_waits():
    assert decide(pr(mergeable="clean"), runs=ci(conclusion="failure"))["reason"] == "REVIEW_REPAIR_CI_FAILED"
    assert decide(pr(mergeable="clean"))["reason"] == "REVIEW_REPAIR_CI_MISSING"
    assert decide(pr(mergeable="clean"), [dict(repair(), created_at="2026-09-25T14:25:00Z")])[
        "reason"] == "awaiting_current_sha_ci"


def test_no_untrusted_repair_and_human_wait_is_untouched():
    assert decide(pr(), [repair(user="stranger")])["reason"] == "missing_trusted_repair_record"
    state = pr()
    state["labels"].append({"name": "status:review"})
    assert decide(state)["action"] == "noop"


def test_owner_recovery_observation_is_never_a_review_pass():
    observation = dict(repair(), body=repair()["body"].replace(
        "<!-- agent-repair:v1 -->", "<!-- repair-ci-wait:v1 -->"
    ))
    assert decide(pr(status="todo"), [observation])["reason"] == "REVIEW_REPAIR_MERGE_CONFLICT"


def test_preexisting_conflict_blocker_recovers_only_from_its_exact_observation():
    state = pr(status="blocked", mergeable="clean")
    state["labels"] = [x for x in state["labels"] if x["name"] != "recovery:repair-ci"]
    observation = dict(repair(), body=repair()["body"].replace(
        "<!-- agent-repair:v1 -->",
        "<!-- repair-ci-wait:v1 -->\nblocker_code=REVIEW_REPAIR_MERGE_CONFLICT",
    ))
    assert decide(state, [observation], ci())["action"] == "requeue_review"
    assert decide(state, [repair()], ci())["reason"] == "unrelated_blocker"
    state["labels"].append({"name": "blocker:content"})
    assert decide(state, [observation], ci())["reason"] == "unrelated_blocker"
