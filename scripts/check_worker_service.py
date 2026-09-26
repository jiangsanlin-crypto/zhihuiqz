"""Read-only account-worker integration preflight; never starts work or dispatches."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx


async def check_service(url, token, *, transport=None, expected_sha=None, expected_repository=None):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
        or parsed.query or parsed.fragment or not token or '\n' in token or '\r' in token):
        raise ValueError('HTTPS service URL and valid dedicated bearer required')
    result = {'status': 'BLOCKED', 'checks': [], 'execution_started': False}
    async with httpx.AsyncClient(base_url=url.rstrip('/') + '/',
        headers={'Authorization': 'Bearer ' + token}, timeout=15,
        follow_redirects=False, transport=transport) as client:
        if expected_sha is not None or expected_repository is not None:
            item = {'endpoint': 'readyz', 'status': 'BLOCKED'}
            try:
                response = await client.get('readyz')
                response.raise_for_status()
                data = response.json()
                if (isinstance(data, dict) and data.get('protocol') == 'shared-claims:v1'
                    and data.get('agents_enabled') is False
                    and (expected_sha is None or data.get('build_sha') == expected_sha)
                    and (expected_repository is None or data.get('repository') == expected_repository)):
                    item['status'] = 'PASS'
                else:
                    item['reason'] = 'SERVICE_IDENTITY_MISMATCH'
            except (httpx.HTTPError, ValueError):
                item['reason'] = 'SERVICE_IDENTITY_UNAVAILABLE'
            result['checks'].append(item)
        for endpoint, field in [('claims/ready', 'candidates'), ('intake/issues', 'issues')]:
            item = {'endpoint': endpoint, 'status': 'BLOCKED'}
            try:
                response = await client.get(endpoint)
                item['http_status'] = response.status_code
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get(field), list):
                    item['reason'] = 'INVALID_PROTOCOL_RESPONSE'
                else:
                    item['status'] = 'PASS'
            except httpx.HTTPStatusError:
                item['reason'] = 'AUTH_OR_ENDPOINT_UNAVAILABLE'
            except (httpx.TransportError, ValueError):
                item['reason'] = 'TRANSPORT_OR_PROTOCOL_FAILURE'
            result['checks'].append(item)
    if all(item['status'] == 'PASS' for item in result['checks']):
        result['status'] = 'PASS'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--token-file', required=True,
                        help='Dedicated claim-service credential file; never an OpenAI credential')
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--repository', required=True)
    args = parser.parse_args()
    try:
        token = Path(args.token_file).read_text().strip()
        result = asyncio.run(check_service(args.url, token, expected_sha=args.expected_sha, expected_repository=args.repository))
    except (OSError, ValueError):
        result = {'status': 'BLOCKED', 'reason': 'INVALID_LOCAL_CONFIGURATION', 'execution_started': False}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
