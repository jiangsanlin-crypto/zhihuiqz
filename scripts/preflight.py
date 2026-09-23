from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx


REQUIRED = {
    "GITHUB_REPOSITORY": "GitHub repository",
    "GITHUB_TOKEN": "Orchestrator GitHub write token",
    "ORCHESTRATOR_TOKEN": "GitHub-to-Orchestrator bearer token",
    "WORKBUDDY_URL": "WorkBuddy runner URL",
}


def load_env_file(path: str | None) -> dict[str, str]:
    values = dict(os.environ)
    if not path:
        return values

    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(path)

    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key.strip(), value.strip())

    return values


def oauth_configured(env: dict[str, str]) -> bool:
    return bool(env.get("WORKBUDDY_ACCESS_TOKEN")) or all(
        env.get(key)
        for key in (
            "WORKBUDDY_CLIENT_ID",
            "WORKBUDDY_CLIENT_SECRET",
            "WORKBUDDY_REFRESH_TOKEN",
        )
    )


def static_checks(
    env: dict[str, str],
) -> list[tuple[str, bool, str]]:
    results = []

    for key, description in REQUIRED.items():
        results.append(
            (
                key,
                bool(env.get(key)),
                description,
            )
        )

    configured = oauth_configured(env)
    results.append(
        (
            "WORKBUDDY_MODE",
            True,
            (
                "full: real cloud dispatch enabled"
                if configured
                else (
                    "degraded: OAuth is optional for bootstrap; real cloud "
                    "dispatch is disabled"
                )
            ),
        )
    )

    model_ok = (
        env.get("WORKBUDDY_MODEL") == "GLM-5.3-Flash"
        and env.get(
            "WORKBUDDY_MODEL_LOCK_CONFIRMED",
            "",
        ).strip().lower() in {"1", "true", "yes", "on"}
    )
    results.append(
        (
            "WORKBUDDY_MODEL_LOCK",
            model_ok,
            "GLM-5.3-Flash must be the only enabled/default model in the dedicated WorkBuddy app",
        )
    )

    return results


async def fetch_health(
    name: str,
    base_url: str,
) -> tuple[str, bool, str]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                base_url.rstrip("/") + "/healthz"
            )
            response.raise_for_status()
            data = response.json()
        return name, bool(data.get("ok")), str(data)
    except Exception as exc:
        return (
            name,
            False,
            f"{type(exc).__name__}: {exc}",
        )


def print_results(
    results: list[tuple[str, bool, str]],
) -> bool:
    ok_all = True
    for name, ok, detail in results:
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {name}: {detail}")
        ok_all = ok_all and ok
    return ok_all


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate three-agent Orchestrator activation prerequisites."
        )
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--live",
        action="store_true",
        help="also call WorkBuddy /healthz",
    )
    args = parser.parse_args()

    env = load_env_file(args.env_file)
    ok = print_results(static_checks(env))

    if args.live and ok:
        ok = print_results(
            [
                await fetch_health(
                    "workbuddy_health",
                    env["WORKBUDDY_URL"],
                )
            ]
        ) and ok

    if not ok:
        print(
            "Preflight failed. No production action was taken."
        )
        return 1

    print(
        "Preflight passed. Codex/ChatGPT runtime models are "
        "validated by the GitHub workflow policy check."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
