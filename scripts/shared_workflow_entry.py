"""Shared-mode Actions wake bridge.

It never writes GitHub labels or invokes a model. The controller is reached
through either a reviewed HTTPS URL or the repository's protected SSH transport.
"""
import argparse
import json
import os
import re

from shared_transport import request


def wake(*, repository: str, expected_sha: str, source: str, delivery_id: str):
    if not repository or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("invalid shared controller identity")
    identity = request("GET", "/readyz")
    if (
        identity.get("repository") != repository
        or identity.get("build_sha") != expected_sha
        or identity.get("protocol") != "shared-claims:v1"
        or identity.get("writes_enabled") is not True
        or identity.get("agents_enabled") is not False
    ):
        raise ValueError("controller identity or write mode mismatch")
    result = request(
        "POST",
        "/control/wake",
        dict(
            repository=repository,
            expected_build_sha=expected_sha,
            source=source,
            delivery_id=delivery_id,
        ),
    )
    if result.get("status") != "completed" or result.get("execution_started") is not False:
        raise ValueError("unexpected controller receipt")
    return {
        "status": "CONTROLLER_ACKNOWLEDGED",
        "execution_started": False,
        "dispatch_performed": bool(result.get("dispatch_performed")),
        "dispatch_count": int(result.get("dispatch_count") or 0),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", choices=["validator", "planner", "reconciler", "watchdog"], required=True
    )
    args = parser.parse_args()
    try:
        result = wake(
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            expected_sha=os.environ.get("CONTROL_BUILD_SHA", ""),
            source=args.source,
            delivery_id=(
                f"actions:{os.environ.get('GITHUB_RUN_ID','')}:"
                f"{os.environ.get('GITHUB_RUN_ATTEMPT','')}:{args.source}"
            ),
        )
    except (RuntimeError, ValueError, KeyError, TypeError):
        print(json.dumps({"status": "BLOCKED", "reason": "SHARED_CONTROLLER_UNAVAILABLE_OR_REJECTED"}))
        raise SystemExit(1)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
