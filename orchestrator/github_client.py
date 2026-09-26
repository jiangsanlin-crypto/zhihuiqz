from __future__ import annotations

import base64
from typing import Any, Iterable
from urllib.parse import quote

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
            "GET", f"{self.base}/repos/{repo}/issues/{number}"
        )
        data = response.json()
        return [
            str(item.get("name")) for item in (data.get("labels") or [])
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

    async def get_pr_snapshot(self, repo: str, number: int) -> dict[str, Any]:
        response = await self._request(
            "GET", f"{self.base}/repos/{repo}/pulls/{number}"
        )
        return response.json()

    async def list_open_prs(self, repo: str) -> list[dict]:
        items, page = [], 1
        while True:
            response = await self._request("GET", f"{self.base}/repos/{repo}/pulls",
                params={"state": "open", "sort": "created", "direction": "asc",
                        "per_page": 100, "page": page})
            batch = response.json()
            if not isinstance(batch, list):
                raise ValueError("GitHub pull requests response is not a list")
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1

    async def list_open_issues(self, repo: str) -> list[dict]:
        items, page = [], 1
        while True:
            response = await self._request("GET", f"{self.base}/repos/{repo}/issues",
                params={"state": "open", "sort": "created", "direction": "asc", "per_page": 100, "page": page})
            batch = response.json()
            if not isinstance(batch, list):
                raise ValueError("GitHub issues response is not a list")
            items.extend(x for x in batch if "pull_request" not in x)
            if len(batch) < 100:
                return items
            page += 1

    async def get_publication_commit(self, repo: str, sha: str) -> dict:
        """Read the immutable commit and every changed path (fail on truncation)."""
        result, files, page = None, [], 1
        while True:
            response = await self._request("GET", f"{self.base}/repos/{repo}/commits/{sha}",
                params={"per_page": 100, "page": page})
            data = response.json()
            if result is None:
                result = data
            batch = data.get("files")
            if not isinstance(batch, list):
                raise ValueError("commit paths unavailable")
            files.extend(batch)
            if len(files) >= 3000:
                raise ValueError("commit path listing may be truncated")
            if len(batch) < 100:
                result["files"] = files
                return result
            page += 1

    async def list_workflow_runs(self, repo: str, head_sha: str) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        page = 1
        while True:
            response = await self._request(
                "GET", f"{self.base}/repos/{repo}/actions/runs",
                params={"head_sha": head_sha, "per_page": 100, "page": page},
            )
            batch = response.json().get("workflow_runs")
            if not isinstance(batch, list):
                raise ValueError("GitHub workflow runs response is not a list")
            runs.extend(batch)
            if len(batch) < 100:
                return {"workflow_runs": runs}
            page += 1

    async def _matches_published_report(
        self, repo: str, live_sha: str, expected_parent: str,
        changes: list[FileChange], message_prefix: str,
    ) -> bool:
        """Accept only an exact report commit published before a worker crash."""
        response = await self._request(
            "GET", f"{self.base}/repos/{repo}/commits/{live_sha}"
        )
        data = response.json()
        parents = [
            str(parent.get("sha") or "") for parent in data.get("parents", [])
            if isinstance(parent, dict)
        ]
        paths = [change.path for change in changes]
        actual = [
            str(item.get("filename") or "") for item in data.get("files", [])
            if isinstance(item, dict)
        ]
        if (parents != [expected_parent]
            or not str((data.get("commit") or {}).get("message") or "").startswith(
                f"{message_prefix}:"
            )
            or len(paths) != len(set(paths))
            or sorted(paths) != sorted(actual)):
            return False
        for change in changes:
            content_response = await self._request(
                "GET", f"{self.base}/repos/{repo}/contents/{quote(change.path, safe='/')}",
                params={"ref": live_sha},
            )
            content_data = content_response.json()
            if content_data.get("encoding") != "base64":
                return False
            encoded = "".join(str(content_data.get("content") or "").splitlines())
            try:
                published = base64.b64decode(encoded, validate=True).decode("utf-8")
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
        """Commit all report files once, only if the PR head is still expected.

        A Contents API PUT can silently include an unrelated concurrent push
        to another path. A commit created with the exact expected parent and
        a non-forced ref update rejects that diverging push instead.
        """
        files = list(changes)
        paths = [change.path for change in files]
        if len(set(paths)) != len(paths) or any(
            not path.startswith("reports/") or path.endswith("/") or any(
                segment in {"", ".", ".."} for segment in path.split("/")
            ) for path in paths
        ):
            raise ValueError("invalid or duplicate report path")

        url = f"{self.base}/repos/{repo}"

        async def live_pr() -> dict[str, Any]:
            data = await self.get_pr_snapshot(repo, pr_number)
            head = data.get("head") or {}
            base = data.get("base") or {}
            if (data.get("state") != "open" or data.get("merged_at")
                or (head.get("repo") or {}).get("full_name") != repo
                or head.get("ref") in {"main", base.get("ref")}
                or not head.get("ref") or not head.get("sha")):
                raise RuntimeError("PR_BRANCH_IDENTITY_CHANGED")
            return data

        original = await live_pr()
        branch = original["head"]["ref"]
        expected = expected_head_sha or original["head"]["sha"]
        if original["head"]["sha"] != expected:
            if expected_head_sha and await self._matches_published_report(
                repo, str(original["head"]["sha"]), expected, files,
                message_prefix,
            ):
                return str(original["head"]["sha"])
            raise RuntimeError("CONCURRENT_BRANCH_ADVANCE: initial head changed")
        if not files:
            return expected

        parent = (await self._request(
            "GET", f"{url}/git/commits/{expected}"
        )).json()
        tree_entries = []
        for change in files:
            blob = (await self._request(
                "POST", f"{url}/git/blobs",
                json={
                    "content": base64.b64encode(change.content.encode()).decode(),
                    "encoding": "base64",
                },
            )).json()
            tree_entries.append({
                "path": change.path, "mode": "100644", "type": "blob",
                "sha": blob["sha"],
            })
        tree = (await self._request(
            "POST", f"{url}/git/trees",
            json={"base_tree": parent["tree"]["sha"], "tree": tree_entries},
        )).json()
        if tree["sha"] == parent["tree"]["sha"]:
            # Re-running QA with identical reports must not manufacture a new
            # HEAD and invalidate the completed independent review forever.
            unchanged = await live_pr()
            if (unchanged["head"]["sha"] != expected
                or unchanged["head"]["ref"] != branch
                or unchanged["base"]["ref"] != original["base"]["ref"]):
                raise RuntimeError("CONCURRENT_BRANCH_ADVANCE: unchanged reports")
            return expected
        commit = (await self._request(
            "POST", f"{url}/git/commits",
            json={
                "message": f"{message_prefix}: update {len(files)} report file(s)",
                "tree": tree["sha"], "parents": [expected],
            },
        )).json()
        new_sha = str(commit["sha"])

        # A branch change between blob creation and this ref update must never
        # cause a partial file write. An unrelated descendant of expected is
        # not an ancestor of this newly created commit, so non-force rejects it.
        before_write = await live_pr()
        if (before_write["head"]["sha"] != expected
            or before_write["head"]["ref"] != branch
            or before_write["base"]["ref"] != original["base"]["ref"]):
            raise RuntimeError("CONCURRENT_BRANCH_ADVANCE: before ref update")
        ref = (await self._request(
            "PATCH", f"{url}/git/refs/heads/{quote(branch, safe='/')}",
            json={"sha": new_sha, "force": False},
        )).json()
        if (ref.get("object") or {}).get("sha") != new_sha:
            raise RuntimeError("PR_REF_UPDATE_UNVERIFIED")
        final = await live_pr()
        if (final["head"]["sha"] != new_sha
            or final["head"]["ref"] != branch
            or final["base"]["ref"] != original["base"]["ref"]):
            raise RuntimeError("CONCURRENT_BRANCH_ADVANCE: after ref update")
        return new_sha

    async def get_default_branch(self, repo: str) -> str:
        response = await self._request('GET', f'{self.base}/repos/{repo}')
        response.raise_for_status()
        return response.json()['default_branch']
