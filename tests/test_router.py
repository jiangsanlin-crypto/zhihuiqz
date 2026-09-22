from orchestrator.task_router import build,next_labels


def test_workbuddy():
    p={
        "action":"labeled",
        "number":12,
        "label":{"name":"agent:workbuddy"},
        "issue":{"labels":[{"name":"agent:workbuddy"},{"name":"status:todo"}]},
    }
    req,_=build("issues",p,"a/b")
    assert req.agent=="workbuddy"


def test_qa():
    p={
        "action":"labeled",
        "number":8,
        "label":{"name":"agent:sandbox"},
        "pull_request":{"labels":[{"name":"agent:sandbox"},{"name":"needs:qa"},{"name":"status:todo"}]},
    }
    req,_=build("pull_request",p,"a/b")
    assert req.agent=="sandbox"


def test_codex_transition():
    labels=next_labels(
        "codex",
        "pull_request",
        ["agent:codex","status:running"],
        "success",
        [],
    )
    assert "agent:sandbox" in labels
    assert "needs:qa" in labels
    assert "status:todo" in labels


def test_second_sandbox_gate_goes_to_workbuddy_review():
    labels=next_labels(
        "sandbox",
        "pull_request",
        ["agent:sandbox","needs:qa","status:running"],
        "success",
        [],
    )
    assert "agent:workbuddy" in labels
    assert "status:review" in labels
