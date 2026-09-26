"""Call one authenticated shared-controller endpoint.

The JSON request body is read from --json, --json-file, or stdin. Output is one
JSON object. Secret values are never written to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys

from shared_transport import request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", choices=["GET", "POST"])
    parser.add_argument("path")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json")
    group.add_argument("--json-file")
    args = parser.parse_args()

    payload = None
    if args.json is not None:
        payload = json.loads(args.json)
    elif args.json_file is not None:
        payload = json.load(open(args.json_file))
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            payload = json.loads(raw)

    result = request(args.method, args.path, payload)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
