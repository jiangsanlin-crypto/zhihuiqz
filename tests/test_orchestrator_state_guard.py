from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orchestrator import main


def run_state_guard(monkeypatch, labels):
    async def safe_head(req, expected_sha):
        assert expected_sha == "abc123"

    async def live_labels(repository, source_number):
        return labels

    monkeypatch.setattr(main, "require_current_head", safe_head)
    monkeypatch.setattr(main.github, "get_issue_labels", live_labels)
    req = SimpleNamespace(repository="owner/repo", source_number=78)
    expected = {"agent:workbuddy", "phase:qa", "status:running"}
    return main.require_current_state(req, "abc123", expected)


def test_current_state_accepts_exact_workflow_and_preserves_unrelated(monkeypatch):
    labels = asyncio.run(run_state_guard(monkeypatch, [
        "agent:workbuddy", "phase:qa", "status:running", "keep:me",
    ]))
    assert "keep:me" in labels


@pytest.mark.parametrize("labels", [
    ["status:review", "approval:production-required"],
    ["agent:workbuddy", "phase:qa", "status:running", "status:todo"],
    ["agent:workreview", "phase:code-review", "status:running"],
])
def test_current_state_rejects_superseded_workflow(monkeypatch, labels):
    with pytest.raises(RuntimeError, match="WORKFLOW_STATE_SUPERSEDED"):
        asyncio.run(run_state_guard(monkeypatch, labels))


def test_projection_preserves_latest_unrelated_labels_and_removes_old_state():
    labels = main.project_workflow_labels(
        ["agent:workbuddy", "phase:qa", "status:running", "status:todo",
         "domain:billing", "priority:p1"],
        {"status:review", "approval:production-required"},
    )
    assert labels == [
        "approval:production-required", "domain:billing", "priority:p1",
        "status:review",
    ]


def test_handoff_gate_block_keeps_concurrent_unrelated_label(monkeypatch, tmp_path):
    req = SimpleNamespace(
        task_id="GH-ISSUE-77", agent="workbuddy", repository="owner/repo",
        source_kind="pull_request", source_number=78,
        phase="phase:qa", source_sha="abc123",
    )
    snapshots = iter([
        ["agent:workbuddy", "phase:qa", "status:todo"],
        ["agent:workbuddy", "phase:qa", "status:todo"],
        ["agent:workbuddy", "phase:qa", "status:todo", "keep:concurrent"],
    ])
    written = []

    async def current_state(req, source_sha, workflow):
        return next(snapshots)

    async def list_comments(repository, source_number):
        return []

    async def comment(repository, source_number, body):
        return None

    async def set_labels(repository, source_number, labels):
        written.append(labels)

    async def snapshot(*args):
        return dict(state='open', head={'sha':'abc123','ref':'feature','repo':{'full_name':'owner/repo'}},
            base={'ref':'main'}, labels=written[-1] if written else
            ['agent:workbuddy','phase:qa','status:todo','keep:concurrent'])
    monkeypatch.setattr(main, "github", SimpleNamespace(
        configured=True, list_comments=list_comments, get_pr_snapshot=snapshot,
        comment=comment, set_labels=set_labels,
    ))
    from orchestrator.state_store import StateStore
    store=StateStore(str(tmp_path/'state.db'))
    store.enqueue('delivery-1','pull_request',{})
    monkeypatch.setattr(main,'store',store)
    monkeypatch.setattr(main, "require_current_state", current_state)
    monkeypatch.setattr(main, "build", lambda *args: (
        req, ["agent:workbuddy", "phase:qa", "status:todo"],
    ))

    asyncio.run(main.process(store.claim_next()))
    assert written == [[
        "agent:workbuddy", "keep:concurrent", "phase:qa", "recovery:qa-evidence", "status:blocked",
    ]]
