#! /usr/bin/env python

import websockets
import json
import asyncio
import time
from collections import defaultdict

GATEWAY_URL = 'ws://127.0.0.1:28333/ws'
GATEWAY_AUTH = '<auth>'
NODE_URL = 'ws://localhost:8546/'
known_txs = {}
stats = defaultdict(list)

async def gw_loop():
    global stats
    async with websockets.connect(GATEWAY_URL, extra_headers={'Authorization': GATEWAY_AUTH}) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "subscribe", 
            # "params": ["newTxs", {"include": ["tx_contents", "local_region"]}]
            "params": ["newTxs", {"include": ["tx_hash"]}]
        }))
        while True:
            r = json.loads(await ws.recv())
            if 'params' in r:
                h = r['params']['result']['txHash']
                ts = time.monotonic()
                delay = 0
                if h in known_txs:
                    delay = (ts-known_txs[h])*1000
                else:
                    known_txs[h] = ts
                stats['GW'].append(delay)

async def pending_loop():
    global stats
    async with websockets.connect(NODE_URL) as ws:
        await ws.send(json.dumps({
            'id': 'log_loop',
            'method': 'eth_subscribe',
            'params': ['newPendingTransactions']
        }))
        while True:
            r = json.loads(await ws.recv())
            if 'params' in r:
                h = r['params']['result']
                ts = time.monotonic()
                delay = 0
                if h in known_txs:
                    delay = (ts-known_txs[h])*1000
                else:
                    known_txs[h] = ts
                stats['GETH'].append(delay)

async def stats_writer():
    global stats
    while True:
        await asyncio.sleep(5)
        print(sum(stats['GW'])/len(stats['GW']), len(stats['GW']), sum(stats['GETH'])/len(stats['GETH']), len(stats['GETH']))
        stats = defaultdict(list)

async def main():
    await asyncio.gather(
        pending_loop(),
        gw_loop(),
        stats_writer(),
    )

if __name__ == '__main__':
    asyncio.run(main())
