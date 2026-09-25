from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orchestrator import main


def identity(**overrides):
    value = {
        "head_ref": "feature",
        "head_sha": "abc123",
        "head_repo_full_name": "owner/repo",
        "base_ref": "main",
        "default_branch": "main",
    }
    value.update(overrides)
    return value


def run_guard(monkeypatch, live):
    async def current_head(repository, source_number):
        assert repository == "owner/repo"
        assert source_number == 78
        return live

    monkeypatch.setattr(main.github, "get_pr_head_identity", current_head)
    req = SimpleNamespace(repository="owner/repo", source_number=78)
    return main.require_current_head(req, "abc123")


def test_require_current_head_accepts_exact_safe_revision(monkeypatch):
    asyncio.run(run_guard(monkeypatch, identity()))


def test_require_current_head_rejects_concurrent_advance(monkeypatch):
    with pytest.raises(
        RuntimeError,
        match="CONCURRENT_BRANCH_ADVANCE: expected=abc123 live=new456",
    ):
        asyncio.run(run_guard(monkeypatch, identity(head_sha="new456")))


def test_require_current_head_rejects_fork_repository(monkeypatch):
    with pytest.raises(RuntimeError, match="UNSAFE_PR_HEAD_REPOSITORY"):
        asyncio.run(
            run_guard(
                monkeypatch,
                identity(head_repo_full_name="attacker/fork"),
            )
        )


def test_require_current_head_rejects_default_branch(monkeypatch):
    with pytest.raises(RuntimeError, match="UNSAFE_PR_HEAD_BRANCH: main"):
        asyncio.run(run_guard(monkeypatch, identity(head_ref="main")))
