from __future__ import annotations

import asyncio

import pytest

from orchestrator.github_client import GitHubClient
from orchestrator.models import FileChange


def change(path: str) -> FileChange:
    return FileChange(path=path, content="new content")


def test_update_pr_files_tracks_each_owned_commit(monkeypatch):
    client = GitHubClient("token")
    heads = iter(["start", "commit-1", "commit-2"])
    commits = iter(["commit-1", "commit-2"])
    writes = []

    async def branch(repo, number):
        return "feature"

    async def head(repo, number):
        return next(heads)

    async def upsert(repo, branch_name, item, prefix):
        writes.append(item.path)
        return next(commits)

    monkeypatch.setattr(client, "get_pr_head_branch", branch)
    monkeypatch.setattr(client, "get_pr_head_sha", head)
    monkeypatch.setattr(client, "_upsert_file", upsert)

    result = asyncio.run(
        client.update_pr_files(
            "owner/repo",
            78,
            [change("a.txt"), change("b.txt")],
            expected_head_sha="start",
        )
    )

    assert result == "commit-2"
    assert writes == ["a.txt", "b.txt"]


def test_update_pr_files_stops_between_commits_on_foreign_advance(monkeypatch):
    client = GitHubClient("token")
    heads = iter(["start", "foreign"])
    writes = []

    async def branch(repo, number):
        return "feature"

    async def head(repo, number):
        return next(heads)

    async def upsert(repo, branch_name, item, prefix):
        writes.append(item.path)
        return "commit-1"

    monkeypatch.setattr(client, "get_pr_head_branch", branch)
    monkeypatch.setattr(client, "get_pr_head_sha", head)
    monkeypatch.setattr(client, "_upsert_file", upsert)

    with pytest.raises(
        RuntimeError,
        match="CONCURRENT_BRANCH_ADVANCE: expected=commit-1 live=foreign",
    ):
        asyncio.run(
            client.update_pr_files(
                "owner/repo",
                78,
                [change("a.txt"), change("b.txt")],
                expected_head_sha="start",
            )
        )

    assert writes == ["a.txt"]
