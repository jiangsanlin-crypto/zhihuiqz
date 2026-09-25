from __future__ import annotations

from typing import Any, Iterable

import httpx

from .models import FileChange


class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base = "https://api.github.com"

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.request(
                method,
                url,
                headers=self._headers(),
                **kwargs,
            )
        response.raise_for_status()
        return response

    async def comment(self, repo: str, number: int, body: str) -> None:
        await self._request(
            "POST",
            f"{self.base}/repos/{repo}/issues/{number}/comments",
            json={"body": body},
        )

    async def set_labels(self, repo: str, number: int, labels: list[str]) -> None:
        await self._request(
            "PUT",
            f"{self.base}/repos/{repo}/issues/{number}/labels",
            json={"labels": labels},
        )

    async def list_comments(self, repo: str, number: int) -> list[dict]:
        comments: list[dict] = []
        page = 1
        while True:
            response = await self._request(
                "GET",
                f"{self.base}/repos/{repo}/issues/{number}/comments",
                params={"per_page": 100, "page": page},
            )
            batch = response.json()
            if not isinstance(batch, list):
                raise ValueError("GitHub comments response is not a list")
            comments.extend(batch)
            if len(batch) < 100:
                return comments
            page += 1

    async def repository_dispatch(
        self,
        repo: str,
        event_type: str,
        client_payload: dict[str, Any],
    ) -> None:
        await self._request(
            "POST",
            f"{self.base}/repos/{repo}/dispatches",
            json={
                "event_type": event_type,
                "client_payload": client_payload,
            },
        )

    async def get_issue_body(self, repo: str, number: int) -> str:
        response = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/issues/{number}",
        )
        data = response.json()
        return str(data.get("body") or "")

    async def get_pr_head_branch(self, repo: str, number: int) -> str:
        response = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/pulls/{number}",
        )
        data = response.json()
        return str(data["head"]["ref"])

    async def get_pr_head_sha(self, repo: str, number: int) -> str:
        response = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/pulls/{number}",
        )
        data = response.json()
        return str(data["head"]["sha"])

    async def _create_tree_commit(
        self,
        repo: str,
        expected_head_sha: str,
        changes: list[FileChange],
        message_prefix: str,
    ) -> str:
        base = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/git/commits/{expected_head_sha}",
        )
        base_tree_sha = str(base.json()["tree"]["sha"])
        entries = []

        for change in changes:
            blob = await self._request(
                "POST",
                f"{self.base}/repos/{repo}/git/blobs",
                json={"content": change.content, "encoding": "utf-8"},
            )
            entries.append(
                {
                    "path": change.path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": str(blob.json()["sha"]),
                }
            )

        tree = await self._request(
            "POST",
            f"{self.base}/repos/{repo}/git/trees",
            json={"base_tree": base_tree_sha, "tree": entries},
        )
        commit = await self._request(
            "POST",
            f"{self.base}/repos/{repo}/git/commits",
            json={
                "message": (
                    f"{message_prefix}: "
                    + ", ".join(change.path for change in changes)
                ),
                "tree": str(tree.json()["sha"]),
                "parents": [expected_head_sha],
            },
        )
        return str(commit.json()["sha"])

    async def update_pr_files(
        self,
        repo: str,
        pr_number: int,
        changes: Iterable[FileChange],
        message_prefix: str = "reports: WorkBuddy handoff",
        expected_head_sha: str | None = None,
    ) -> str:
        branch = await self.get_pr_head_branch(repo, pr_number)
        expected = expected_head_sha or await self.get_pr_head_sha(repo, pr_number)
        pending = list(changes)
        if not pending:
            return expected

        live_sha = await self.get_pr_head_sha(repo, pr_number)
        if live_sha != expected:
            raise RuntimeError(
                "CONCURRENT_BRANCH_ADVANCE: "
                f"expected={expected} live={live_sha}"
            )

        # Build one commit whose only parent is the reviewed revision. Objects are
        # not visible on the PR branch until the final non-force ref update.
        commit_sha = await self._create_tree_commit(
            repo,
            expected,
            pending,
            message_prefix,
        )

        # Close the object-creation race. If another actor advanced the branch,
        # leave the new commit unreachable and do not mutate the PR ref.
        live_sha = await self.get_pr_head_sha(repo, pr_number)
        if live_sha != expected:
            raise RuntimeError(
                "CONCURRENT_BRANCH_ADVANCE: "
                f"expected={expected} live={live_sha}"
            )

        await self._request(
            "PATCH",
            f"{self.base}/repos/{repo}/git/refs/heads/{branch}",
            json={"sha": commit_sha, "force": False},
        )

        live_sha = await self.get_pr_head_sha(repo, pr_number)
        if live_sha != commit_sha:
            raise RuntimeError(
                "CONCURRENT_BRANCH_ADVANCE: "
                f"expected={commit_sha} live={live_sha}"
            )
        return commit_sha
