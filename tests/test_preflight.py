from scripts.preflight import static_checks


def as_map(results):
    return {name: ok for name, ok, _ in results}


def test_preflight_accepts_refresh_token_configuration():
    env = {
        "GITHUB_REPOSITORY": "a/b",
        "GITHUB_TOKEN": "x",
        "ORCHESTRATOR_TOKEN": "x",
        "WORKBUDDY_URL": "http://workbuddy",
        "WORKBUDDY_TOKEN": "x",
        "SANDBOX_URL": "http://sandbox",
        "SANDBOX_TOKEN": "x",
        "WORKBUDDY_CLIENT_ID": "id",
        "WORKBUDDY_CLIENT_SECRET": "secret",
        "WORKBUDDY_REFRESH_TOKEN": "refresh",
    }
    result = as_map(static_checks(env))
    assert all(result.values())


def test_preflight_rejects_missing_workbuddy_oauth():
    env = {
        "GITHUB_REPOSITORY": "a/b",
        "GITHUB_TOKEN": "x",
        "ORCHESTRATOR_TOKEN": "x",
        "WORKBUDDY_URL": "http://workbuddy",
        "WORKBUDDY_TOKEN": "x",
        "SANDBOX_URL": "http://sandbox",
        "SANDBOX_TOKEN": "x",
    }
    result = as_map(static_checks(env))
    assert result["WORKBUDDY_OAUTH"] is False
