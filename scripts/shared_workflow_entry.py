"""Shared-mode Actions bridge. It never writes GitHub labels or invokes a model."""
import argparse
import asyncio
import json
import os
import re
from urllib.parse import urlsplit
import httpx

async def wake(*,url,token,repository,expected_sha,source,delivery_id,transport=None):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
        or parsed.query or parsed.fragment or not token or any(c.isspace() for c in token)
        or not re.fullmatch('[0-9a-f]{40}',expected_sha)):
        raise ValueError('invalid shared controller configuration')
    async with httpx.AsyncClient(base_url=url.rstrip('/')+'/',headers={'Authorization':'Bearer '+token},
                                 timeout=120,follow_redirects=False,transport=transport) as client:
        ready=await client.get('readyz');ready.raise_for_status();identity=ready.json()
        if (not isinstance(identity,dict) or identity.get('repository')!=repository or identity.get('build_sha')!=expected_sha
            or identity.get('protocol')!='shared-claims:v1' or identity.get('writes_enabled') is not True
            or identity.get('agents_enabled') is not False):
            raise ValueError('controller identity or write mode mismatch')
        response=await client.post('control/wake',json=dict(repository=repository,expected_build_sha=expected_sha,
            source=source,delivery_id=delivery_id))
        response.raise_for_status();result=response.json()
        if (not isinstance(result,dict) or result.get('status')!='completed' or result.get('execution_started') is not False
            or result.get('dispatch_performed') is not False):raise ValueError('unexpected controller receipt')
        return {'status':'CONTROLLER_ACKNOWLEDGED','execution_started':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=['validator','planner','reconciler','watchdog'],required=True)
    args=parser.parse_args()
    try:
        result=asyncio.run(wake(url=os.environ.get('CONTROL_SERVICE_URL',''),
            token=os.environ.get('CONTROL_SERVICE_TOKEN',''),repository=os.environ.get('GITHUB_REPOSITORY',''),
            expected_sha=os.environ.get('CONTROL_BUILD_SHA',''),source=args.source,
            delivery_id=f"actions:{os.environ.get('GITHUB_RUN_ID','')}:{os.environ.get('GITHUB_RUN_ATTEMPT','')}:{args.source}"))
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        print(json.dumps({'status':'BLOCKED','reason':'SHARED_CONTROLLER_UNAVAILABLE_OR_REJECTED'}))
        raise SystemExit(1)
    print(json.dumps(result))

if __name__=='__main__':main()
