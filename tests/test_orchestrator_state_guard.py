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
