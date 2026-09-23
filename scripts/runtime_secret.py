from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def bundle_values() -> dict[str, str]:
    encoded = os.getenv("ORCH_ENV_B64", "").strip()
    if not encoded:
        return {}
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception as exc:
        raise SystemExit(f"ORCH_ENV_B64 is invalid: {type(exc).__name__}")
    return parse_env(decoded)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key")
    parser.add_argument("--fallback-env")
    parser.add_argument("--output-name", default="value")
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT", ""))
    args = parser.parse_args()

    value = ""
    if args.fallback_env:
        value = os.getenv(args.fallback_env, "").strip()
    if not value:
        value = bundle_values().get(args.key, "").strip()

    if not value:
        print(f"missing runtime secret: {args.key}")
        return 1

    print(f"::add-mask::{value}")

    if not args.github_output:
        raise SystemExit("GITHUB_OUTPUT is unavailable")

    path = Path(args.github_output)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{args.output_name}<<__SECRET__\n{value}\n__SECRET__\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
