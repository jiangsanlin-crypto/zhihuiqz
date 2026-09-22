from __future__ import annotations

import base64
from typing import Iterable

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

    async def _default_branch_and_sha(self, repo: str) -> tuple[str, str]:
        info = (await self._request("GET", f"{self.base}/repos/{repo}")).json()
        default = info["default_branch"]
        branch = (
            await self._request(
                "GET",
                f"{self.base}/repos/{repo}/branches/{default}",
            )
        ).json()
        return default, branch["commit"]["sha"]

    async def _ensure_branch(self, repo: str, branch: str, base_sha: str) -> None:
        ref_url = f"{self.base}/repos/{repo}/git/ref/heads/{branch}"
        async with httpx.AsyncClient(timeout=30) as client:
            existing = await client.get(ref_url, headers=self._headers())
        if existing.status_code == 200:
            return
        if existing.status_code != 404:
            existing.raise_for_status()
        await self._request(
            "POST",
            f"{self.base}/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )

    async def _upsert_file(self, repo: str, branch: str, change: FileChange) -> None:
        url = f"{self.base}/repos/{repo}/contents/{change.path}"
        async with httpx.AsyncClient(timeout=30) as client:
            current = await client.get(
                url,
                headers=self._headers(),
                params={"ref": branch},
            )
        payload = {
            "message": f"docs: WorkBuddy update {change.path}",
            "content": base64.b64encode(change.content.encode()).decode(),
            "branch": branch,
        }
        if current.status_code == 200:
            payload["sha"] = current.json()["sha"]
        elif current.status_code != 404:
            current.raise_for_status()
        await self._request("PUT", url, json=payload)

    async def _find_open_pr(self, repo: str, branch: str) -> int | None:
        owner = repo.split("/", 1)[0]
        response = await self._request(
            "GET",
            f"{self.base}/repos/{repo}/pulls",
            params={
                "state": "open",
                "head": f"{owner}:{branch}",
                "per_page": 10,
            },
        )
        items = response.json()
        return int(items[0]["number"]) if items else None

    async def create_or_update_spec_pr(
        self,
        repo: str,
        issue_number: int,
        task_id: str,
        title: str,
        changes: Iterable[FileChange],
    ) -> int:
        default, base_sha = await self._default_branch_and_sha(repo)
        branch = f"agent/workbuddy/issue-{issue_number}"
        await self._ensure_branch(repo, branch, base_sha)

        for change in changes:
            await self._upsert_file(repo, branch, change)

        existing = await self._find_open_pr(repo, branch)
        if existing:
            return existing

        response = await self._request(
            "POST",
            f"{self.base}/repos/{repo}/pulls",
            json={
                "title": f"spec: {title[:180]}",
                "head": branch,
                "base": default,
                "body": (
                    f"<!-- agent-task-id:{task_id} -->\n"
                    f"WorkBuddy specification handoff for issue #{issue_number}.\n\n"
                    "This PR must pass Sandbox QA, Codex implementation, "
                    "final Sandbox QA, WorkBuddy final review, and human approval.\n\n"
                    f"Closes #{issue_number}"
                ),
            },
        )
        return int(response.json()["number"])
