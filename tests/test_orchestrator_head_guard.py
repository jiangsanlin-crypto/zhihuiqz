from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orchestrator import main


def test_require_current_head_accepts_exact_revision(monkeypatch):
    async def current_head(repository, source_number):
        assert repository == "owner/repo"
        assert source_number == 78
        return "abc123"

    monkeypatch.setattr(main.github, "get_pr_head_sha", current_head)
    req = SimpleNamespace(repository="owner/repo", source_number=78)

    asyncio.run(main.require_current_head(req, "abc123"))


def test_require_current_head_rejects_concurrent_advance(monkeypatch):
    async def advanced_head(repository, source_number):
        return "new456"

    monkeypatch.setattr(main.github, "get_pr_head_sha", advanced_head)
    req = SimpleNamespace(repository="owner/repo", source_number=78)

    with pytest.raises(
        RuntimeError,
        match="CONCURRENT_BRANCH_ADVANCE: expected=abc123 live=new456",
    ):
        asyncio.run(main.require_current_head(req, "abc123"))
