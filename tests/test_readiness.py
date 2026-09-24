from orchestrator.config import Settings
from orchestrator.readiness import all_ok, failed_check_names, static_checks


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


def test_failed_check_names_returns_failed_names_sorted():
    checks = {
        "db": {"ok": False},
        "api": {"ok": True},
        "cache": {"ok": 0},
    }
    assert failed_check_names(checks) == ["cache", "db"]


def test_failed_check_names_treats_missing_ok_as_failed():
    checks = {
        "healthy": {"ok": True},
        "missing": {},
        "empty": {"ok": ""},
    }
    assert failed_check_names(checks) == ["empty", "missing"]
