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

    async def _upsert_file(
        self,
        repo: str,
        branch: str,
        change: FileChange,
        message_prefix: str,
    ) -> None:
        url = f"{self.base}/repos/{repo}/contents/{change.path}"
        async with httpx.AsyncClient(timeout=30) as client:
            current = await client.get(
                url,
                headers=self._headers(),
                params={"ref": branch},
            )

        payload = {
            "message": f"{message_prefix}: {change.path}",
            "content": base64.b64encode(change.content.encode()).decode(),
            "branch": branch,
        }

        if current.status_code == 200:
            payload["sha"] = current.json()["sha"]
        elif current.status_code != 404:
            current.raise_for_status()

        await self._request("PUT", url, json=payload)

    async def update_pr_files(
        self,
        repo: str,
        pr_number: int,
        changes: Iterable[FileChange],
        message_prefix: str = "reports: WorkBuddy handoff",
    ) -> str:
        branch = await self.get_pr_head_branch(repo, pr_number)
        for change in changes:
            await self._upsert_file(
                repo,
                branch,
                change,
                message_prefix,
            )
        return await self.get_pr_head_sha(repo, pr_number)
