from orchestrator.config import Settings
from orchestrator.readiness import all_ok, static_checks


def test_static_readiness_passes_with_required_config():
    settings = Settings(
        github_token="token",
        github_repository="a/b",
        orchestrator_token="orchestrator",
        workbuddy_url="http://workbuddy",
        workbuddy_token="workbuddy-token",
        workbuddy_model="GLM-5.3-Flash",
        workbuddy_model_lock_confirmed=True,
    )
    checks = static_checks(settings)
    assert all_ok(checks)


def test_static_readiness_fails_without_model_confirmation():
    settings = Settings(
        github_token="token",
        github_repository="a/b",
        orchestrator_token="orchestrator",
        workbuddy_url="http://workbuddy",
        workbuddy_token="workbuddy-token",
        workbuddy_model="GLM-5.3-Flash",
        workbuddy_model_lock_confirmed=False,
    )
    checks = static_checks(settings)
    assert checks["workbuddy_model"]["ok"] is False
    assert all_ok(checks) is False


def test_live_readiness_allows_degraded_without_oauth():
    from orchestrator.readiness import workbuddy_live_check

    check, mode, configured = workbuddy_live_check(
        {
            "ok": True,
            "oauth_configured": False,
            "expected_model": "GLM-5.3-Flash",
            "model_lock_confirmed": True,
        }
    )
    assert check["ok"] is True
    assert mode == "degraded"
    assert configured is False
