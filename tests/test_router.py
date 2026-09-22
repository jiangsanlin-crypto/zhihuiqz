from orchestrator.task_router import build, next_labels


def test_issue_routes_to_workbuddy():
    payload = {
        "action": "labeled",
        "number": 12,
        "label": {"name": "agent:workbuddy"},
        "issue": {
            "labels": [
                {"name": "agent:workbuddy"},
                {"name": "status:todo"},
            ]
        },
    }
    req, _ = build("issues", payload, "a/b")
    assert req.agent == "workbuddy"
    assert req.task_id == "GH-ISSUE-12"


def test_pr_preserves_original_task_id():
    payload = {
        "action": "labeled",
        "number": 8,
        "label": {"name": "agent:sandbox"},
        "pull_request": {
            "body": "<!-- agent-task-id:GH-ISSUE-12 -->",
            "head": {
                "ref": "agent/workbuddy/issue-12",
                "sha": "abc123",
            },
            "labels": [{"name": "agent:sandbox"}],
        },
    }
    req, _ = build("pull_request", payload, "a/b")
    assert req.agent == "sandbox"
    assert req.task_id == "GH-ISSUE-12"
    assert req.source_sha == "abc123"


def test_status_label_does_not_retrigger_agent():
    payload = {
        "action": "labeled",
        "number": 8,
        "label": {"name": "status:running"},
        "pull_request": {
            "labels": [
                {"name": "agent:sandbox"},
                {"name": "status:running"},
            ]
        },
    }
    assert build("pull_request", payload, "a/b") is None


def test_first_sandbox_hands_to_codex():
    labels = next_labels(
        "sandbox",
        "pull_request",
        ["agent:sandbox", "status:running"],
        "success",
        [],
    )
    assert "agent:codex" in labels
    assert "status:todo" in labels


def test_final_sandbox_hands_to_workbuddy():
    labels = next_labels(
        "sandbox",
        "pull_request",
        ["agent:sandbox", "needs:qa", "status:running"],
        "success",
        [],
    )
    assert "agent:workbuddy" in labels
    assert "status:review" in labels
    assert "needs:qa" not in labels


def test_blocked_final_qa_preserves_retry_phase():
    labels = next_labels(
        "sandbox",
        "pull_request",
        ["agent:sandbox", "needs:qa", "status:running"],
        "blocked",
        [],
    )
    assert "agent:sandbox" in labels
    assert "needs:qa" in labels
    assert "status:blocked" in labels
