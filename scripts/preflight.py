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
    "WORKBUDDY_TOKEN": "WorkBuddy runner bearer token",
    "SANDBOX_URL": "Sandbox runner URL",
    "SANDBOX_TOKEN": "Sandbox runner bearer token",
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


def static_checks(env: dict[str, str]) -> list[tuple[str, bool, str]]:
    results = []
    for key, description in REQUIRED.items():
        ok = bool(env.get(key))
        results.append((key, ok, description))

    oauth_ok = bool(env.get("WORKBUDDY_ACCESS_TOKEN")) or all(
        env.get(key)
        for key in (
            "WORKBUDDY_CLIENT_ID",
            "WORKBUDDY_CLIENT_SECRET",
            "WORKBUDDY_REFRESH_TOKEN",
        )
    )
    results.append(
        (
            "WORKBUDDY_OAUTH",
            oauth_ok,
            "access token or client_id/client_secret/refresh_token",
        )
    )
    return results


async def fetch_health(name: str, base_url: str) -> tuple[str, bool, str]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(base_url.rstrip("/") + "/healthz")
            response.raise_for_status()
            data = response.json()
        ok = bool(data.get("ok"))
        return name, ok, str(data)
    except Exception as exc:
        return name, False, f"{type(exc).__name__}: {exc}"


async def live_checks(env: dict[str, str]) -> list[tuple[str, bool, str]]:
    return await asyncio.gather(
        fetch_health("workbuddy_health", env["WORKBUDDY_URL"]),
        fetch_health("sandbox_health", env["SANDBOX_URL"]),
    )


def print_results(results: list[tuple[str, bool, str]]) -> bool:
    ok_all = True
    for name, ok, detail in results:
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {name}: {detail}")
        ok_all = ok_all and ok
    return ok_all


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate multi-agent orchestration activation prerequisites."
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--live",
        action="store_true",
        help="also call WorkBuddy and Sandbox /healthz endpoints",
    )
    args = parser.parse_args()

    env = load_env_file(args.env_file)
    static = static_checks(env)
    ok = print_results(static)

    if args.live and ok:
        live = await live_checks(env)
        ok = print_results(live) and ok

    if not ok:
        print("Preflight failed. No production action was taken.")
        return 1

    print("Preflight passed. The system is ready for a manual E2E smoke run.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
