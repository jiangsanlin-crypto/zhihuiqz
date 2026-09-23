import asyncio

import pytest
from fastapi import HTTPException

from orchestrator import workbuddy_runner as runner
from orchestrator.models import AgentRunRequest


def request():
    return AgentRunRequest(
        task_id="JOB-002",
        agent="workbuddy",
        repository="a/b",
        source_kind="pull_request",
        source_number=36,
        event_name="pull_request",
        prompt_path="agents/workbuddy_prompt.md",
        phase="phase:prototype",
    )


def test_runner_returns_503_before_cloud_dispatch_without_oauth(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RUNNER_TOKEN", "runner-token")
    monkeypatch.setattr(runner, "ALLOWED_REPO", "")
    monkeypatch.setattr(runner, "EXPECTED_MODEL", "GLM-5.3-Flash")
    monkeypatch.setattr(runner, "MODEL_LOCK_CONFIRMED", True)
    monkeypatch.setattr(runner, "WB_ACCESS_TOKEN", "")
    monkeypatch.setattr(runner, "WB_REFRESH_TOKEN", "")
    monkeypatch.setattr(runner, "WB_CLIENT_ID", "")
    monkeypatch.setattr(runner, "WB_CLIENT_SECRET", "")
    monkeypatch.setattr(runner, "WB_TOKEN_FILE", tmp_path / "missing.json")

    with pytest.raises(HTTPException) as caught:
        asyncio.run(runner.run(request(), "Bearer runner-token"))

    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "WORKBUDDY_DEGRADED"
    assert caught.value.detail["workbuddy_mode"] == "degraded"


def test_runner_health_reports_degraded_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "WB_ACCESS_TOKEN", "")
    monkeypatch.setattr(runner, "WB_REFRESH_TOKEN", "")
    monkeypatch.setattr(runner, "WB_CLIENT_ID", "")
    monkeypatch.setattr(runner, "WB_CLIENT_SECRET", "")
    monkeypatch.setattr(runner, "WB_TOKEN_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(runner, "EXPECTED_MODEL", "GLM-5.3-Flash")
    monkeypatch.setattr(runner, "MODEL_LOCK_CONFIRMED", True)

    health = asyncio.run(runner.healthz())

    assert health["ok"] is True
    assert health["workbuddy_mode"] == "degraded"
    assert health["workbuddy_configured"] is False
