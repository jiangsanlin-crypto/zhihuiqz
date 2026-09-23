from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["codex", "chatgpt", "workbuddy"]
HandoffTarget = Literal["codex", "chatgpt", "workbuddy", "human"]


class FileChange(BaseModel):
    path: str
    content: str
    purpose: str = ""


class CheckResult(BaseModel):
    name: str
    status: Literal["passed", "failed", "skipped"]
    detail: str = ""


class Handoff(BaseModel):
    version: Literal["1.0"] = "1.0"
    task_id: str
    from_agent: AgentName
    to_agent: HandoffTarget | None = None
    phase: str
    status: Literal["success", "blocked", "failed"]
    summary: str

    model: str | None = None
    effort: str | None = None

    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)

    artifacts: list[str] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    source_ref: str | None = None
    source_sha: str | None = None
    pr_number: int | None = None


class AgentRunRequest(BaseModel):
    task_id: str
    agent: AgentName
    repository: str
    source_kind: Literal["issue", "pull_request"]
    source_number: int
    event_name: str
    action: str | None = None
    prompt_path: str
    phase: str | None = None
    source_ref: str | None = None
    source_sha: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(BaseModel):
    status: Literal["success", "blocked", "failed"]
    summary: str
    artifacts: list[str] = Field(default_factory=list)
    changes: list[FileChange] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    next_labels: list[str] = Field(default_factory=list)
    pr_number: int | None = None
    handoff: Handoff | None = None
