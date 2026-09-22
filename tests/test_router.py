from orchestrator.task_router import build,next_labels
def test_workbuddy():
    p={"action":"labeled","number":12,"issue":{"labels":[{"name":"agent:workbuddy"},{"name":"status:todo"}]}}
    req,_=build("issues",p,"a/b"); assert req.agent=="workbuddy"
def test_qa():
    p={"action":"labeled","number":8,"pull_request":{"labels":[{"name":"needs:qa"}]}}
    req,_=build("pull_request",p,"a/b"); assert req.agent=="sandbox"
def test_codex_transition():
    labels=next_labels("codex","issue",["agent:codex","status:running"],"success",[])
    assert "needs:qa" in labels and "status:review" in labels
