from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orchestrator.github_client import GitHubClient
from orchestrator.models import FileChange


def change(path: str) -> FileChange:
    return FileChange(path=path, content="new content")


def test_update_pr_files_publishes_one_non_force_commit(monkeypatch):
    client = GitHubClient("token")
    heads = iter(["start", "start", "commit-1"])
    created = []
    ref_updates = []

    async def branch(repo, number):
        return "feature"

    async def head(repo, number):
        return next(heads)

    async def create_commit(repo, parent, changes, prefix):
        created.append((parent, [item.path for item in changes]))
        return "commit-1"

    async def request(method, url, **kwargs):
        ref_updates.append((method, url, kwargs["json"]))
        return SimpleNamespace(json=lambda: {})

    monkeypatch.setattr(client, "get_pr_head_branch", branch)
    monkeypatch.setattr(client, "get_pr_head_sha", head)
    monkeypatch.setattr(client, "_create_tree_commit", create_commit)
    monkeypatch.setattr(client, "_request", request)

    result = asyncio.run(
        client.update_pr_files(
            "owner/repo",
            78,
            [change("a.txt"), change("b.txt")],
            expected_head_sha="start",
        )
    )

    assert result == "commit-1"
    assert created == [("start", ["a.txt", "b.txt"])]
    assert ref_updates == [
        (
            "PATCH",
            "https://api.github.com/repos/owner/repo/git/refs/heads/feature",
            {"sha": "commit-1", "force": False},
        )
    ]


def test_update_pr_files_stops_before_ref_update_on_foreign_advance(monkeypatch):
    client = GitHubClient("token")
    heads = iter(["start", "foreign"])
    ref_updates = []

    async def branch(repo, number):
        return "feature"

    async def head(repo, number):
        return next(heads)

    async def create_commit(repo, parent, changes, prefix):
        return "commit-1"

    async def request(method, url, **kwargs):
        ref_updates.append((method, url))
        return SimpleNamespace(json=lambda: {})

    monkeypatch.setattr(client, "get_pr_head_branch", branch)
    monkeypatch.setattr(client, "get_pr_head_sha", head)
    monkeypatch.setattr(client, "_create_tree_commit", create_commit)
    monkeypatch.setattr(client, "_request", request)

    with pytest.raises(
        RuntimeError,
        match="CONCURRENT_BRANCH_ADVANCE: expected=start live=foreign",
    ):
        asyncio.run(
            client.update_pr_files(
                "owner/repo",
                78,
                [change("a.txt"), change("b.txt")],
                expected_head_sha="start",
            )
        )

    assert ref_updates == []
