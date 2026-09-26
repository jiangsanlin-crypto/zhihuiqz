import asyncio
from types import SimpleNamespace

from orchestrator.control_dispatch import dispatch_ready
from orchestrator.state_store import StateStore

SHA = "a" * 40


def test_planner_dispatch_is_automatic_and_cooldown_idempotent(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    store.observe_issue(
        "owner/repo",
        80,
        "b" * 64,
        "awaiting_planner",
        {"task_id": "GH-ISSUE-80", "linked_prs": [], "ambiguous_prs": []},
    )
    sent = []

    async def repository_dispatch(repo, event_type, payload):
        sent.append((repo, event_type, payload))

    async def list_open_prs(repo):
        return []

    github = SimpleNamespace(
        repository_dispatch=repository_dispatch,
        list_open_prs=list_open_prs,
    )
    settings = SimpleNamespace(github_repository="owner/repo")

    assert asyncio.run(dispatch_ready(store, github, settings, SHA)) == 1
    assert sent[0][1] == "shared_codex_product"
    assert sent[0][2]["issue_number"] == 80
    assert sent[0][2]["control_build_sha"] == SHA
    assert asyncio.run(dispatch_ready(store, github, settings, SHA)) == 0
    assert len(sent) == 1


def test_validator_dispatch_is_derived_from_live_ready_projection(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    sent = []
    pr = {
        "number": 83,
        "state": "open",
        "draft": False,
        "body": "<!-- agent-task-id:GH-ISSUE-80 -->",
        "labels": ["agent:workbuddy", "phase:prototype", "status:todo"],
        "head": {
            "sha": SHA,
            "ref": "feature",
            "repo": {"full_name": "owner/repo", "default_branch": "main"},
        },
        "base": {"ref": "main"},
    }

    async def repository_dispatch(repo, event_type, payload):
        sent.append((repo, event_type, payload))

    async def list_open_prs(repo):
        return [pr]

    github = SimpleNamespace(
        repository_dispatch=repository_dispatch,
        list_open_prs=list_open_prs,
    )
    settings = SimpleNamespace(github_repository="owner/repo")

    assert asyncio.run(dispatch_ready(store, github, settings, SHA)) == 1
    assert sent == [(
        "owner/repo",
        "shared_validator_prototype",
        {
            "repository": "owner/repo",
            "pr_number": 83,
            "source_sha": SHA,
            "head_ref": "feature",
            "task_id": "GH-ISSUE-80",
            "phase": "phase:prototype",
            "control_build_sha": SHA,
            "dispatch_key": f"validator:83:{SHA}:phase:prototype",
        },
    )]
