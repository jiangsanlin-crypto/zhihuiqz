from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orchestrator import main


def test_require_current_head_accepts_exact_revision(monkeypatch):
    async def current_head(repository, source_number):
        assert repository == "owner/repo"
        assert source_number == 78
        return {"state": "open", "merged_at": None,
                "head": {"sha": "abc123", "ref": "feature",
                         "repo": {"full_name": "owner/repo"}},
                "base": {"ref": "main"}}

    monkeypatch.setattr(main.github, "get_pr_snapshot", current_head)
    req = SimpleNamespace(repository="owner/repo", source_number=78,
                          source_ref="feature")

    asyncio.run(main.require_current_head(req, "abc123"))


def test_require_current_head_rejects_concurrent_advance(monkeypatch):
    async def advanced_head(repository, source_number):
        return {"state": "open", "merged_at": None,
                "head": {"sha": "new456", "ref": "feature",
                         "repo": {"full_name": "owner/repo"}},
                "base": {"ref": "main"}}

    monkeypatch.setattr(main.github, "get_pr_snapshot", advanced_head)
    req = SimpleNamespace(repository="owner/repo", source_number=78,
                          source_ref="feature")

    with pytest.raises(
        RuntimeError,
        match="CONCURRENT_BRANCH_ADVANCE: expected=abc123 live=new456",
    ):
        asyncio.run(main.require_current_head(req, "abc123"))


@pytest.mark.parametrize("head_repo,head_ref", [
    ("foreign/fork", "feature"), ("owner/repo", "main"),
    ("owner/repo", "renamed-branch"),
])
def test_require_current_head_rejects_unsafe_branch_identity(
    monkeypatch, head_repo, head_ref,
):
    async def same_sha_wrong_identity(repository, source_number):
        return {"state": "open", "merged_at": None,
                "head": {"sha": "abc123", "ref": head_ref,
                         "repo": {"full_name": head_repo}},
                "base": {"ref": "main"}}

    monkeypatch.setattr(main.github, "get_pr_snapshot", same_sha_wrong_identity)
    req = SimpleNamespace(repository="owner/repo", source_number=78,
                          source_ref="feature")
    with pytest.raises(RuntimeError, match="PR_BRANCH_IDENTITY_CHANGED"):
        asyncio.run(main.require_current_head(req, "abc123"))
