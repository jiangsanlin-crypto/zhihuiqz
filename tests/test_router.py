from orchestrator.task_router import build, next_labels


def pr_payload(phase: str):
    return {"action":"labeled","number":8,"label":{"name":"agent:workbuddy"},"pull_request":{"body":"<!-- agent-task-id:GH-ISSUE-12 -->","head":{"ref":"agent/codex/issue-12","sha":"abc123"},"labels":[{"name":"agent:workbuddy"},{"name":phase},{"name":"status:todo"}]}}


def test_prototype_routes_to_workbuddy():
    req, _ = build("pull_request", pr_payload("phase:prototype"), "a/b")
    assert req.agent == "workbuddy" and req.phase == "phase:prototype" and req.task_id == "GH-ISSUE-12"


def test_qa_routes_to_workbuddy():
    req, _ = build("pull_request", pr_payload("phase:qa"), "a/b")
    assert req.phase == "phase:qa"


def test_non_workbuddy_agent_is_not_routed_by_orchestrator():
    payload = pr_payload("phase:implementation")
    payload["label"]["name"] = "agent:chatgpt"
    payload["pull_request"]["labels"][0]["name"] = "agent:chatgpt"
    assert build("pull_request", payload, "a/b") is None


def test_prototype_success_hands_to_chatgpt():
    labels = next_labels("workbuddy","pull_request",["agent:workbuddy","phase:prototype","status:running"],"success",[],phase="phase:prototype")
    assert "agent:chatgpt" in labels and "phase:implementation" in labels


def test_qa_release_enabled_hands_to_codex_release():
    labels = next_labels("workbuddy","pull_request",["agent:workbuddy","phase:qa","status:running"],"success",[],phase="phase:qa",terminal_policy_text="terminal_policy: release_enabled")
    assert "agent:codex" in labels and "phase:release" in labels and "status:todo" in labels


def test_qa_owner_approval_stops_in_review():
    labels = next_labels("workbuddy","pull_request",["agent:workbuddy","phase:qa","status:running"],"success",[],phase="phase:qa",terminal_policy_text="terminal_policy: owner_approval_required")
    assert labels == ["approval:production-required", "status:review"]


def test_qa_missing_policy_fails_closed():
    labels = next_labels("workbuddy","pull_request",["agent:workbuddy","phase:qa","status:running"],"success",[],phase="phase:qa")
    assert "status:review" in labels and "phase:release" not in labels


def test_blocked_workbuddy_preserves_phase():
    labels = next_labels("workbuddy","pull_request",["agent:workbuddy","phase:qa","status:running"],"blocked",[],phase="phase:qa")
    assert "agent:workbuddy" in labels and "phase:qa" in labels and "status:blocked" in labels


def test_workbuddy_requires_status_todo():
    payload = pr_payload("phase:prototype")
    payload["pull_request"]["labels"]=[{"name":"agent:workbuddy"},{"name":"phase:prototype"},{"name":"status:running"}]
    assert build("pull_request",payload,"a/b") is None


def test_deploy_routes_to_workbuddy():
    req,_=build("pull_request",pr_payload("phase:deploy"),"a/b")
    assert req.agent == "workbuddy" and req.phase == "phase:deploy"


def test_deploy_success_hands_to_execution_state():
    labels=next_labels("workbuddy","pull_request",["agent:workbuddy","phase:deploy","status:running"],"success",[],phase="phase:deploy")
    assert "agent:workbuddy" in labels and "phase:deploy" in labels and "status:running" in labels


def test_qa_stop_after_qa_never_routes_release():
    labels = next_labels("workbuddy","pull_request",["agent:workbuddy","phase:qa","status:running"],"success",[],phase="phase:qa",terminal_policy_text="terminal_policy: stop_after_qa")
    assert labels == ["approval:production-required", "status:review"]
    assert "agent:codex" not in labels and "phase:release" not in labels


def test_qa_conflicting_policy_fails_closed_without_release():
    labels = next_labels("workbuddy","pull_request",["agent:workbuddy","phase:qa","status:running"],"success",[],phase="phase:qa",terminal_policy_text="terminal_policy: release_enabled\nterminal_policy: owner_approval_required")
    assert "status:review" in labels
    assert "agent:codex" not in labels and "phase:release" not in labels
