from orchestrator.config import Settings
from orchestrator.readiness import all_ok, static_checks


def test_static_readiness_passes_with_required_orchestrator_config():
    settings = Settings(
        github_token="token",
        github_repository="a/b",
        orchestrator_token="orchestrator",
        workbuddy_url="http://workbuddy",
        workbuddy_token="workbuddy-token",
        sandbox_url="http://sandbox",
        sandbox_token="sandbox-token",
    )
    checks = static_checks(settings)
    assert all_ok(checks)


def test_static_readiness_fails_without_write_token():
    settings = Settings(
        github_repository="a/b",
        orchestrator_token="orchestrator",
        workbuddy_url="http://workbuddy",
        workbuddy_token="workbuddy-token",
        sandbox_url="http://sandbox",
        sandbox_token="sandbox-token",
    )
    checks = static_checks(settings)
    assert checks["github_write_token"]["ok"] is False
    assert all_ok(checks) is False
