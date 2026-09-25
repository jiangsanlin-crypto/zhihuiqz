from __future__ import annotations

import base64

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

    async def get_issue_labels(self, repo: str, number: int) -> list[str]:
        response = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/issues/{number}",
        )
        data = response.json()
        return [
            str(item.get("name"))
            for item in (data.get("labels") or [])
            if isinstance(item, dict) and item.get("name")
        ]

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

    async def get_pr_head_identity(self, repo: str, number: int) -> dict[str, str]:
        response = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/pulls/{number}",
        )
        data = response.json()
        head = data.get("head") or {}
        base = data.get("base") or {}
        head_repo = head.get("repo") or {}
        base_repo = base.get("repo") or {}
        return {
            "head_ref": str(head.get("ref") or ""),
            "head_sha": str(head.get("sha") or ""),
            "head_repo_full_name": str(head_repo.get("full_name") or ""),
            "base_ref": str(base.get("ref") or ""),
            "default_branch": str(base_repo.get("default_branch") or ""),
        }

    async def get_pr_head_branch(self, repo: str, number: int) -> str:
        return (await self.get_pr_head_identity(repo, number))["head_ref"]

    async def get_pr_head_sha(self, repo: str, number: int) -> str:
        return (await self.get_pr_head_identity(repo, number))["head_sha"]

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

    async def _matches_published_report(
        self,
        repo: str,
        live_sha: str,
        expected_parent: str,
        changes: list[FileChange],
        message_prefix: str,
    ) -> bool:
        """Recognize only the exact report commit prepared by an interrupted run."""
        response = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/commits/{live_sha}",
        )
        data = response.json()
        parents = [
            str(parent.get("sha") or "")
            for parent in (data.get("parents") or [])
            if isinstance(parent, dict)
        ]
        message = str((data.get("commit") or {}).get("message") or "")
        requested_paths = [change.path for change in changes]
        published_paths = [
            str(item.get("filename") or "")
            for item in (data.get("files") or [])
            if isinstance(item, dict)
        ]
        if (
            parents != [expected_parent]
            or not message.startswith(f"{message_prefix}:")
            or len(requested_paths) != len(set(requested_paths))
            or set(published_paths) != set(requested_paths)
            or len(published_paths) != len(requested_paths)
        ):
            return False

        for change in changes:
            content_response = await self._request(
                "GET",
                f"{self.base}/repos/{repo}/contents/{change.path}",
                params={"ref": live_sha},
            )
            content_data = content_response.json()
            if content_data.get("encoding") != "base64":
                return False
            encoded = str(content_data.get("content") or "").replace("\\n", "")
            try:
                published = base64.b64decode(encoded, validate=True).decode()
            except (ValueError, UnicodeDecodeError):
                return False
            if published != change.content:
                return False
        return True

    async def update_pr_files(
        self,
        repo: str,
        pr_number: int,
        changes: Iterable[FileChange],
        message_prefix: str = "reports: WorkBuddy handoff",
        expected_head_sha: str | None = None,
    ) -> str:
        identity = await self.get_pr_head_identity(repo, pr_number)
        branch = identity["head_ref"]
        expected = expected_head_sha or identity["head_sha"]
        protected = {identity["base_ref"], identity["default_branch"]} - {""}
        if identity["head_repo_full_name"] != repo:
            raise RuntimeError(
                "UNSAFE_PR_HEAD_REPOSITORY: "
                f"expected={repo} live={identity['head_repo_full_name']}"
            )
        if not branch or branch in protected:
            raise RuntimeError(f"UNSAFE_PR_HEAD_BRANCH: {branch or '<empty>'}")

        pending = list(changes)
        if not pending:
            return expected

        live_sha = identity["head_sha"]
        if live_sha != expected:
            if await self._matches_published_report(
                repo,
                live_sha,
                expected,
                pending,
                message_prefix,
            ):
                return live_sha
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
