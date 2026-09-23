from orchestrator.task_router import build, next_labels


def pr_payload(phase: str):
    return {
        "action": "labeled",
        "number": 8,
        "label": {"name": "agent:workbuddy"},
        "pull_request": {
            "body": "<!-- agent-task-id:GH-ISSUE-12 -->",
            "head": {
                "ref": "agent/codex/issue-12",
                "sha": "abc123",
            },
            "labels": [
                {"name": "agent:workbuddy"},
                {"name": phase},
                {"name": "status:todo"},
            ],
        },
    }


def test_prototype_routes_to_workbuddy():
    req, _ = build(
        "pull_request",
        pr_payload("phase:prototype"),
        "a/b",
    )
    assert req.agent == "workbuddy"
    assert req.phase == "phase:prototype"
    assert req.task_id == "GH-ISSUE-12"


def test_qa_routes_to_workbuddy():
    req, _ = build(
        "pull_request",
        pr_payload("phase:qa"),
        "a/b",
    )
    assert req.phase == "phase:qa"


def test_non_workbuddy_agent_is_not_routed_by_orchestrator():
    payload = pr_payload("phase:implementation")
    payload["label"]["name"] = "agent:chatgpt"
    payload["pull_request"]["labels"][0]["name"] = "agent:chatgpt"
    assert build("pull_request", payload, "a/b") is None


def test_prototype_success_hands_to_chatgpt():
    labels = next_labels(
        "workbuddy",
        "pull_request",
        [
            "agent:workbuddy",
            "phase:prototype",
            "status:running",
        ],
        "success",
        [],
        phase="phase:prototype",
    )
    assert "agent:chatgpt" in labels
    assert "phase:implementation" in labels


def test_qa_success_hands_to_codex_release():
    labels = next_labels(
        "workbuddy",
        "pull_request",
        [
            "agent:workbuddy",
            "phase:qa",
            "status:running",
        ],
        "success",
        [],
        phase="phase:qa",
    )
    assert "agent:codex" in labels
    assert "phase:release" in labels


def test_blocked_workbuddy_preserves_phase():
    labels = next_labels(
        "workbuddy",
        "pull_request",
        [
            "agent:workbuddy",
            "phase:qa",
            "status:running",
        ],
        "blocked",
        [],
        phase="phase:qa",
    )
    assert "agent:workbuddy" in labels
    assert "phase:qa" in labels
    assert "status:blocked" in labels
