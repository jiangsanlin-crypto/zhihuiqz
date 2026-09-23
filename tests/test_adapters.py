import httpx

from orchestrator.adapters import degraded_dispatch_result


def test_degraded_response_suppresses_handoff():
    response = httpx.Response(
        503,
        json={
            "detail": {
                "code": "WORKBUDDY_DEGRADED",
                "message": "real dispatch disabled",
            }
        },
    )

    result = degraded_dispatch_result(response)

    assert result is not None
    assert result.status == "blocked"
    assert result.handoff_allowed is False
