import asyncio
import json
from types import SimpleNamespace

import pytest

from orchestrator import main
from orchestrator.evidence_gate import validate_qa_evidence
from orchestrator.handoff_gate import HandoffGateError
from orchestrator.models import AgentRunResult, FileChange
from scripts.reconcile_handoff_state import decide_reconciliation


def evidence():
    payload = {
        "task_id": "GH-ISSUE-77", "from_agent": "workreview",
        "to_agent": "workbuddy", "phase": "code_review", "source_sha": "sha",
        "status": "success", "blockers": [], "pr_number": 78,
        "checks": [{"name": "independent_code_review", "status": "passed"}],
    }
    comments = [
        {"id": 1, "created_at": "2026-09-25T01:00:00Z", "user": {"login": "owner"},
         "body": "<!-- agent-claim:v1 -->\ntask_id=GH-ISSUE-77\n"
                 "agent=workreview\nphase=code-review\nsource_sha=sha"},
        {"id": 2, "created_at": "2026-09-25T02:00:00Z", "user": {"login": "owner"},
         "body": "<!-- agent-handoff:v1 -->\n```json\n" + json.dumps(payload) + "\n```"},
    ]
    runs = {"workflow_runs": [{
        "id": 10, "created_at": "2026-09-25T00:00:00Z", "head_sha": "sha",
        "head_branch": "feature", "name": "CI", "path": ".github/workflows/ci.yml",
        "event": "pull_request", "status": "completed", "conclusion": "success",
    }]}
    return comments, runs


def validate(comments, runs):
    return validate_qa_evidence(comments, runs, task_id="GH-ISSUE-77",
        head_sha="sha", head_ref="feature", trusted_login="owner", pr_number=78)


@pytest.mark.parametrize("conclusion", ["action_required", "failure", "cancelled", None])
def test_nonpassing_ci_cannot_enter_qa(conclusion):
    comments, runs = evidence()
    runs["workflow_runs"][0]["conclusion"] = conclusion
    with pytest.raises(HandoffGateError, match="ordinary CI"):
        validate(comments, runs)


def test_current_sha_ci_and_independent_claim_are_both_required():
    comments, runs = evidence()
    assert validate(comments, runs)["status"] == "success"
    with pytest.raises(HandoffGateError, match="independent"):
        validate(comments[1:], runs)
    runs["workflow_runs"][0]["head_sha"] = "old"
    with pytest.raises(HandoffGateError, match="ordinary CI"):
        validate(comments, runs)


def test_bot_review_cannot_substitute_for_independent_account_review():
    comments, runs = evidence()
    comments[1]["user"]["login"] = "github-actions[bot]"
    with pytest.raises(HandoffGateError):
        validate(comments, runs)


def test_later_same_second_failure_revokes_review_pass():
    comments, runs = evidence()
    failed = dict(comments[-1], id=3,
                  body=comments[-1]["body"].replace('"status": "success"', '"status": "failed"'))
    with pytest.raises(HandoffGateError, match="not success"):
        validate(comments + [failed], runs)


def test_operation_claim_is_required_before_any_github_side_effect(monkeypatch):
    req = SimpleNamespace(repository="owner/repo", source_number=78,
                          source_sha="sha", phase="phase:qa")
    monkeypatch.setattr(main, "build", lambda *args: (req, []))
    monkeypatch.setattr(main, "github", SimpleNamespace(configured=True))
    monkeypatch.setattr(main, "store", SimpleNamespace(claim_operation=lambda *a: False))
    with pytest.raises(RuntimeError, match="ANOTHER_WORKER_OWNS_LEASE"):
        asyncio.run(main.process({"delivery_id": "b", "lease_id": "lease-b",
                                 "event_name": "pull_request", "payload": {}}))


@pytest.mark.parametrize("conclusion", ["action_required", "success"])
def test_orchestrator_enforces_gate_before_running_adapter(monkeypatch, conclusion):
    comments, runs = evidence()
    runs["workflow_runs"][0]["conclusion"] = conclusion
    writes, starts = [], []
    req = SimpleNamespace(task_id="GH-ISSUE-77", agent="workbuddy",
        repository="owner/repo", source_kind="pull_request", source_number=78,
        phase="phase:qa", source_sha="sha", source_ref="feature")

    async def state(req, sha, workflow):
        return sorted(workflow) + ["keep:me"]

    async def list_comments(*args):
        return comments

    async def list_runs(*args):
        return runs

    async def comment(*args):
        pass

    async def set_labels(repo, number, labels):
        writes.append(labels)

    async def run(req):
        starts.append(req.source_sha)
        raise RuntimeError("TEST_ADAPTER_REACHED")

    monkeypatch.setattr(main, "build", lambda *args: (req, []))
    monkeypatch.setattr(main, "require_current_state", state)
    monkeypatch.setattr(main, "github", SimpleNamespace(configured=True,
        list_comments=list_comments, list_workflow_runs=list_runs,
        comment=comment, set_labels=set_labels))
    monkeypatch.setattr(main, "store", SimpleNamespace(finish=lambda *a, **kw: None))
    monkeypatch.setattr(main, "workbuddy", SimpleNamespace(run=run))
    event = {"delivery_id": "test", "event_name": "pull_request", "payload": {}}
    if conclusion == "success":
        with pytest.raises(RuntimeError, match="TEST_ADAPTER_REACHED"):
            asyncio.run(main.process(event))
        assert starts == ["sha"]
    else:
        asyncio.run(main.process(event))
        assert starts == []
        assert "recovery:qa-evidence" in writes[-1]
        assert "status:blocked" in writes[-1]
        assert "keep:me" in writes[-1]


def test_machine_evidence_blocker_recovers_only_when_both_gates_pass():
    comments, runs = evidence()
    pr = {"number": 78, "state": "open", "head": {"sha": "sha", "ref": "feature"},
          "body": "<!-- agent-task-id:GH-ISSUE-77 -->",
          "labels": ["agent:workbuddy", "phase:qa", "status:blocked",
                     "recovery:qa-evidence", "keep:me"]}
    decision = decide_reconciliation(pr, comments, repository_owner="owner", ci_runs=runs)
    assert decision["action"] == "reconcile"
    assert decision["reason"] == "validated_qa_evidence_resolved"
    assert decision["labels_after"] == ["agent:workbuddy", "keep:me", "phase:qa", "status:todo"]
    assert decide_reconciliation(pr, comments[1:], repository_owner="owner", ci_runs=runs)["action"] == "noop"
    runs["workflow_runs"][0]["conclusion"] = "action_required"
    assert decide_reconciliation(pr, comments, repository_owner="owner", ci_runs=runs)["action"] == "noop"
    runs["workflow_runs"][0]["conclusion"] = "success"
    pr["labels"].append("blocker:content")
    assert decide_reconciliation(pr, comments, repository_owner="owner", ci_runs=runs)["action"] == "noop"


@pytest.mark.parametrize("final_conclusion", ["action_required", "success"])
def test_report_commit_waits_for_final_ci_and_new_review(monkeypatch, final_conclusion):
    comments, initial_runs = evidence()
    state = {"sha": "sha", "labels": ["agent:workbuddy", "phase:qa", "status:todo"]}
    checkpoints, dispatches, adapter_calls = [], [], []

    def request():
        return SimpleNamespace(task_id="GH-ISSUE-77", agent="workbuddy",
            repository="owner/repo", source_kind="pull_request", source_number=78,
            phase="phase:qa", source_sha="sha", source_ref="feature")

    async def snapshot(*args):
        return {"state": "open", "head": {"sha": state["sha"], "ref": "feature",
                "repo": {"full_name": "owner/repo"}}, "base": {"ref": "main"}}

    async def labels(*args):
        return list(state["labels"])

    async def set_labels(repo, number, values):
        state["labels"] = list(values)

    async def list_comments(*args):
        return list(comments)

    async def list_runs(repo, sha):
        if sha == "sha":
            return initial_runs
        return {"workflow_runs": [dict(initial_runs["workflow_runs"][0],
                head_sha="report-sha", conclusion=final_conclusion)]}

    async def comment(repo, number, body):
        comments.append({"user": {"login": "github-actions[bot]"}, "body": body,
                         "created_at": "2026-09-25T03:00:00Z", "id": len(comments) + 1})

    async def issue_body(*args):
        return "terminal_policy: stop_after_qa"

    async def update_files(*args, **kwargs):
        state["sha"] = "report-sha"
        return "report-sha"

    async def dispatch(*args):
        dispatches.append(args)

    async def run(req):
        adapter_calls.append(req.source_sha)
        return AgentRunResult(status="success", summary="QA passed",
            changes=[FileChange(path="reports/qa.md", content="passed")])

    monkeypatch.setattr(main, "build", lambda *args: (request(), []))
    monkeypatch.setattr(main, "github", SimpleNamespace(configured=True,
        get_pr_snapshot=snapshot, get_issue_labels=labels, set_labels=set_labels,
        list_comments=list_comments, list_workflow_runs=list_runs, comment=comment,
        get_issue_body=issue_body, update_pr_files=update_files, repository_dispatch=dispatch))
    monkeypatch.setattr(main, "store", SimpleNamespace(finish=lambda *a, **k: None,
        checkpoint=lambda delivery, payload, **kw: checkpoints.append(payload)))
    monkeypatch.setattr(main, "workbuddy", SimpleNamespace(run=run))
    event = {"delivery_id": "test", "event_name": "pull_request", "payload": {}}
    if final_conclusion != "success":
        with pytest.raises(RuntimeError, match="QA_FINAL_SHA_CI_PENDING"):
            asyncio.run(main.process(event))
        assert "status:running" in state["labels"]
    else:
        asyncio.run(main.process(event))
        assert state["labels"] == ["agent:workreview", "phase:code-review", "status:todo"]
        # Replay after labels were written but before the event was completed.
        asyncio.run(main.process(dict(event, checkpoint=checkpoints[-1])))
        assert adapter_calls == ["sha"]
        assert sum("<!-- qa-postwrite-review:v1 -->" in c["body"] for c in comments) == 1
    assert "status:review" not in state["labels"]
    assert dispatches == []
