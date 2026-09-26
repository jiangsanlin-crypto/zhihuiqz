import asyncio
import json
import pytest
from test_claim_api import setup, projection_setup, payload, AUTH
from orchestrator.state_writer import write_labels

@pytest.mark.parametrize('target',[
 ['agent:workreview','phase:code-review','status:todo','status:running'],
 ['status:review','approval:production-required','phase:qa'],
 ['status:review','approval:production-required','recovery:qa-evidence']])
def test_single_writer_rejects_illegal_targets(projection_setup,target):
    client,store,pr,github,_,_,writes=projection_setup
    claim=client.post('/claims/acquire',json=payload(),headers=AUTH).json()
    binding=json.loads(store.get(claim['delivery_id'])['payload_json'])
    with pytest.raises(RuntimeError,match='AMBIGUOUS'):
        asyncio.run(write_labels(store,github,binding,claim['delivery_id'],claim['lease_id'],pr['labels'],target))
    assert not writes

def test_single_writer_rechecks_human_wait_before_put(projection_setup):
    client,store,pr,github,_,_,writes=projection_setup
    claim=client.post('/claims/acquire',json=payload(),headers=AUTH).json()
    binding=json.loads(store.get(claim['delivery_id'])['payload_json'])
    before=pr['labels'][:]
    pr['labels']=['status:review','approval:production-required']
    with pytest.raises(RuntimeError,match='STATE_CHANGED'):
        asyncio.run(write_labels(store,github,binding,claim['delivery_id'],claim['lease_id'],before,
                                 ['agent:workreview','phase:code-review','status:running']))
    assert not writes
