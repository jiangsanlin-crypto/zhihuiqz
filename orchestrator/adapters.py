from __future__ import annotations

from typing import Any

import httpx

from .models import AgentRunRequest, AgentRunResult


class HttpAgentAdapter:
    def __init__(self, name: str, url: str, token: str):
        self.name = name
        self.url = url.rstrip("/")
        self.token = token

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)

    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def health(self) -> dict[str, Any]:
        if not self.url:
            return {
                "ok": False,
                "agent": self.name,
                "error": "runner URL is not configured",
            }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.url}/healthz")
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict):
                raise ValueError("health response is not an object")
            return data
        except Exception as exc:
            return {
                "ok": False,
                "agent": self.name,
                "error": f"{type(exc).__name__}: {exc}",
            }

    async def run(self, req: AgentRunRequest) -> AgentRunResult:
        if not self.url:
            return AgentRunResult(
                status="blocked",
                summary=f"{self.name} runner is not configured",
            )
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.url}/run",
                    headers=self.headers(),
                    json=req.model_dump(),
                )
                response.raise_for_status()
                return AgentRunResult.model_validate(response.json())
        except Exception as exc:
            return AgentRunResult(
                status="failed",
                summary=(
                    f"{self.name} runner request failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )
