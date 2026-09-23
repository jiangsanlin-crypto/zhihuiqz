from orchestrator.config import Settings
from orchestrator.readiness import all_ok, static_checks


def test_static_readiness_passes_with_required_config():
    settings = Settings(
        github_token="token",
        github_repository="a/b",
        orchestrator_token="orchestrator",
    )
    checks = static_checks(settings)
    assert checks["openai_agent_execution"]["ok"] is True
    assert all_ok(checks)


def test_static_readiness_fails_without_github_token():
    settings = Settings(
        github_token="",
        github_repository="a/b",
        orchestrator_token="orchestrator",
    )
    checks = static_checks(settings)
    assert checks["github_write_token"]["ok"] is False
    assert all_ok(checks) is False
