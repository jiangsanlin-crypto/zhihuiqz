from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace

import pytest

from orchestrator.github_client import GitHubClient
from orchestrator.models import FileChange


def client_with_fake_github(monkeypatch, *, advance_before_ref=False, reject_ref=False):
    client = GitHubClient("test-token")
    calls = []
    head = "old-head"

    async def request(method, url, **kwargs):
        nonlocal head
        calls.append((method, url, kwargs.get("json")))
        if method == "GET" and url.endswith("/pulls/7"):
            current = "concurrent-head" if advance_before_ref and len([
                call for call in calls if call[0] == "GET" and call[1].endswith("/pulls/7")
            ]) > 1 else head
            result = {
                "state": "open", "merged_at": None,
                "base": {"ref": "main"},
                "head": {"sha": current, "ref": "feature/reports",
                         "repo": {"full_name": "owner/repo"}},
            }
        elif method == "GET" and url.endswith("/git/commits/old-head"):
            result = {"tree": {"sha": "old-tree"}}
        elif method == "GET" and url.endswith("/commits/old-head"):
            result = {"parents": [{"sha": "foreign"}],
                      "commit": {"message": ""}, "files": []}
        elif method == "POST" and url.endswith("/git/blobs"):
            result = {"sha": f"blob-{len([x for x in calls if x[1].endswith('/git/blobs')])}"}
        elif method == "POST" and url.endswith("/git/trees"):
            result = {"sha": "new-tree"}
        elif method == "POST" and url.endswith("/git/commits"):
            result = {"sha": "new-head"}
        elif method == "PATCH" and url.endswith("/git/refs/heads/feature/reports"):
            if reject_ref:
                raise RuntimeError("GitHub rejected a non-fast-forward update")
            head = "new-head"
            result = {"object": {"sha": head}}
        else:
            raise AssertionError(f"unexpected GitHub call: {method} {url}")
        return SimpleNamespace(json=lambda: result)

    monkeypatch.setattr(client, "_request", request)
    return client, calls


def test_multiple_report_files_are_one_commit_on_expected_parent(monkeypatch):
    client, calls = client_with_fake_github(monkeypatch)
    changes = [FileChange(path="reports/a.md", content="alpha"),
               FileChange(path="reports/b.md", content="beta")]
    result = asyncio.run(client.update_pr_files(
        "owner/repo", 7, changes, expected_head_sha="old-head"
    ))
    assert result == "new-head"
    commits = [x for x in calls if x[1].endswith("/git/commits") and x[0] == "POST"]
    assert len(commits) == 1
    assert commits[0][2]["parents"] == ["old-head"]
    trees = [x for x in calls if x[1].endswith("/git/trees")]
    assert trees[0][2]["base_tree"] == "old-tree"
    assert {entry["path"] for entry in trees[0][2]["tree"]} == {
        "reports/a.md", "reports/b.md"
    }
    refs = [x for x in calls if x[0] == "PATCH"]
    assert len(refs) == 1 and refs[0][2] == {"sha": "new-head", "force": False}
    assert not any("/contents/" in x[1] for x in calls)


@pytest.mark.parametrize("advance_before_ref,reject_ref", [(True, False), (False, True)])
def test_concurrent_advance_never_partially_writes_pr_branch(
    monkeypatch, advance_before_ref, reject_ref,
):
    client, calls = client_with_fake_github(
        monkeypatch, advance_before_ref=advance_before_ref, reject_ref=reject_ref
    )
    with pytest.raises(RuntimeError, match="CONCURRENT_BRANCH_ADVANCE|non-fast-forward"):
        asyncio.run(client.update_pr_files(
            "owner/repo", 7, [FileChange(path="reports/a.md", content="alpha")],
            expected_head_sha="old-head",
        ))
    if advance_before_ref:
        assert not any(call[0] == "PATCH" for call in calls)
    assert not any("/contents/" in call[1] for call in calls)


def test_stale_initial_head_and_duplicate_paths_fail_closed(monkeypatch):
    client, calls = client_with_fake_github(monkeypatch)
    with pytest.raises(RuntimeError, match="initial head changed"):
        asyncio.run(client.update_pr_files(
            "owner/repo", 7, [FileChange(path="a", content="x")],
            expected_head_sha="stale",
        ))
    assert len(calls) == 1
    with pytest.raises(ValueError, match="duplicate"):
        asyncio.run(client.update_pr_files(
            "owner/repo", 7, [FileChange(path="a", content="x"),
                              FileChange(path="a", content="y")],
            expected_head_sha="old-head",
        ))


def test_crash_replay_recognizes_only_exact_wrapped_report_commit(monkeypatch):
    client = GitHubClient("test-token")
    calls = []

    async def request(method, url, **kwargs):
        calls.append((method, url))
        if url.endswith("/pulls/7"):
            result = {
                "state": "open", "merged_at": None,
                "base": {"ref": "main"},
                "head": {"sha": "published", "ref": "feature/reports",
                         "repo": {"full_name": "owner/repo"}},
            }
        elif url.endswith("/commits/published"):
            result = {
                "parents": [{"sha": "reviewed"}],
                "commit": {"message": "reports: WorkBuddy: update 1 report file(s)"},
                "files": [{"filename": "reports/a.md"}],
            }
        elif url.endswith("/contents/reports/a.md"):
            assert kwargs["params"] == {"ref": "published"}
            result = {
                "encoding": "base64",
                "content": base64.encodebytes(b"alpha" * 30).decode(),
            }
        else:
            raise AssertionError(url)
        return SimpleNamespace(json=lambda: result)

    monkeypatch.setattr(client, "_request", request)
    changes = [FileChange(path="reports/a.md", content="alpha" * 30)]
    assert asyncio.run(client.update_pr_files(
        "owner/repo", 7, changes, message_prefix="reports: WorkBuddy",
        expected_head_sha="reviewed",
    )) == "published"
    assert not any(method in {"POST", "PATCH"} for method, _ in calls)
    with pytest.raises(RuntimeError, match="CONCURRENT_BRANCH_ADVANCE"):
        asyncio.run(client.update_pr_files(
            "owner/repo", 7,
            [FileChange(path="reports/a.md", content="changed")],
            message_prefix="reports: WorkBuddy",
            expected_head_sha="reviewed",
        ))
