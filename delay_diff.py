#! /usr/bin/env python

import websockets
import json
import asyncio
from collections import Counter
from itertools import combinations

GATEWAY_URL = ''
GATEWAY_AUTH = ''

pending_txs = Counter()

async def tx_loop():
    tx_count = 0
    async with websockets.connect(GATEWAY_URL, extra_headers={'Authorization': GATEWAY_AUTH}) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "subscribe", 
            "params": ["newTxs", {"include": ['tx_contents']}]
        }))
        async for event in ws:
            event = json.loads(event)
            if 'params' in event:
                event = event['params']['result']
                tx = event['txContents']
                try:
                    gasPrice = int(tx['gasPrice'], 16)
                except TypeError:
                    print(f"# Error parsing gasPrice={tx['gasPrice']}")
                    continue
                if gasPrice == 3000000000:
                    pending_txs[tx['hash']] = tx_count
                    tx_count += 1

async def block_loop():
    async with websockets.connect(GATEWAY_URL, extra_headers={'Authorization': GATEWAY_AUTH}) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "subscribe", 
            "params": ["newBlocks", {"include": ['header', 'transactions']}]
        }))
        async for event in ws:
            event = json.loads(event)
            if 'params' in event:
                event = event['params']['result']
                miner = event['header']['miner']
                if 'transactions' in event:
                    tx_list = [tx['hash'] for tx in event['transactions'] if tx['hash'] in pending_txs]
                    num_inversions = 0
                    for t1, t2 in combinations(tx_list, 2):
                        if pending_txs[t1] > pending_txs[t2]:
                            num_inversions += 1
                    N = len(tx_list) * (len(tx_list) - 1) / 2
                    if N > 0:
                        print(event['header']['number'], miner, num_inversions/N, len(tx_list))
                    else:
                        print('#', event['header']['number'], miner, 0)
              
async def main():
    await asyncio.gather(
        block_loop(),   
        tx_loop(),
    )

if __name__ == '__main__':
    asyncio.run(main())
