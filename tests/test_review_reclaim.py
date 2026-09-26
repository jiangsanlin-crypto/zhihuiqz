from datetime import datetime, timezone

from scripts.plan_review_reclaim import decide_reclaim


NOW = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)
SHA = "currentsha"


def pr(updated="2026-09-25T12:00:00Z", labels=None):
    return {
        "state": "open", "merged_at": None, "updated_at": updated,
        "head": {"sha": SHA, "ref": "feature"},
        "labels": [{"name": x} for x in (labels or [
            "agent:workreview", "phase:code-review", "status:running"
        ])],
    }


def ci(sha=SHA, conclusion="success"):
    return {"workflow_runs": [{
        "id": 1, "head_sha": sha, "head_branch": "feature",
        "name": "CI", "path": ".github/workflows/ci.yml",
        "event": "pull_request", "status": "completed",
        "conclusion": conclusion, "created_at": "2026-09-25T10:00:00Z",
    }]}


def claim(sha=SHA, created="2026-09-25T13:00:00Z", user="owner"):
    return {
        "user": {"login": user}, "created_at": created,
        "body": f"<!-- agent-claim:v1 -->\ntask_id=GH-ISSUE-77\n"
                f"agent=workreview\nphase=code-review\nsource_sha={sha}",
    }


def test_stale_unowned_review_requeues_same_stage():
    result = decide_reclaim(pr(), [], ci(), now=NOW, owner="owner")
    assert result["action"] == "requeue"
    assert result["labels_after"] == [
        "agent:workreview", "phase:code-review", "status:todo"
    ]


def test_fresh_progress_and_stale_ci_do_not_requeue():
    assert decide_reclaim(pr(), [claim()], ci(), now=NOW, owner="owner")["action"] == "noop"
    assert decide_reclaim(pr(updated="2026-09-25T13:00:00Z"), [], ci(),
                          now=NOW, owner="owner")["action"] == "noop"
    assert decide_reclaim(pr(), [], ci("old"), now=NOW,
                          owner="owner")["reason"] == "current_sha_ci_not_success"
    assert decide_reclaim(pr(), [], ci(conclusion="failure"), now=NOW,
                          owner="owner")["action"] == "noop"
    assert decide_reclaim(pr(), [claim(user="attacker")], ci(),
                          now=NOW, owner="owner")["action"] == "requeue"


def test_review_result_or_owner_wait_never_requeues():
    handoff = {
        "user": {"login": "owner"},
        "body": '<!-- agent-handoff:v1 -->\n```json\n'
                '{"source_sha":"currentsha","from_agent":"workreview",'
                '"phase":"code_review","status":"success"}\n```',
    }
    assert decide_reclaim(pr(), [handoff], ci(), now=NOW,
                          owner="owner")["reason"] == "review_result_exists"
    assert decide_reclaim(pr(labels=[
        "agent:workreview", "phase:code-review", "status:running",
        "status:review", "approval:production-required"
    ]), [], ci(), now=NOW, owner="owner")["action"] == "noop"


def test_unrelated_comments_cannot_keep_a_dead_review_worker_alive():
    old_claim = claim(created="2026-09-25T11:00:00Z")
    other_phase = {
        "user": {"login": "owner"}, "created_at": "2026-09-25T13:25:00Z",
        "body": "<!-- agent-heartbeat:v1 -->\nagent=chatgpt\n"
                "phase=implementation\nsource_sha=currentsha",
    }
    current = pr(updated="2026-09-25T13:25:00Z")
    result = decide_reclaim(current, [old_claim, other_phase], ci(),
                            now=NOW, owner="owner")
    assert result["action"] == "requeue"
    assert result["last_progress_at"] == "2026-09-25T11:00:00+00:00"
    assert decide_reclaim(current, [old_claim, claim()], ci(), now=NOW,
                          owner="owner")["reason"] == "review_may_still_be_active"
