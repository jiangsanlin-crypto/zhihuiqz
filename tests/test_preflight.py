from scripts.preflight import static_checks


def as_map(results):
    return {name: ok for name, ok, _ in results}


def test_preflight_accepts_locked_workbuddy_model():
    env = {
        "GITHUB_REPOSITORY": "a/b",
        "GITHUB_TOKEN": "x",
        "ORCHESTRATOR_TOKEN": "x",
        "WORKBUDDY_URL": "http://workbuddy",
        "WORKBUDDY_TOKEN": "x",
        "WORKBUDDY_CLIENT_ID": "id",
        "WORKBUDDY_CLIENT_SECRET": "secret",
        "WORKBUDDY_REFRESH_TOKEN": "refresh",
        "WORKBUDDY_MODEL": "GLM-5.3-Flash",
        "WORKBUDDY_MODEL_LOCK_CONFIRMED": "true",
    }
    result = as_map(static_checks(env))
    assert all(result.values())


def test_preflight_rejects_unconfirmed_model_lock():
    env = {
        "GITHUB_REPOSITORY": "a/b",
        "GITHUB_TOKEN": "x",
        "ORCHESTRATOR_TOKEN": "x",
        "WORKBUDDY_URL": "http://workbuddy",
        "WORKBUDDY_TOKEN": "x",
        "WORKBUDDY_ACCESS_TOKEN": "token",
        "WORKBUDDY_MODEL": "GLM-5.3-Flash",
        "WORKBUDDY_MODEL_LOCK_CONFIRMED": "false",
    }
    result = as_map(static_checks(env))
    assert result["WORKBUDDY_MODEL_LOCK"] is False
