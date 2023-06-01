#! /usr/bin/env python

import websockets
import json
import asyncio
import time
from collections import defaultdict
import ssl

GATEWAY_URL = 'ws://localhost:28333/ws'
GATEWAY_AUTH = ''
FEED_URL = 'wss://54.157.119.190/ws'
NODE_URL = 'ws://localhost:8546/'

known_txs = {}
stats = defaultdict(list)

async def call_loop(call_queue):
    async with websockets.connect(NODE_URL, max_size=10*2**20) as ws:
        while True:
            method, params, result_queue = await call_queue.get()
            await ws.send(json.dumps({
                'id': 'call_loop',
                'method': method,
                'params': params,
                'jsonrpc': '2.0'
            }))
            response = json.loads(await ws.recv())
            result_queue.put_nowait(response)
            call_queue.task_done()    

async def trace_tx(tx, call_queue, ts):
    q = asyncio.Queue()
    call_queue.put_nowait(('debug_traceCall', [tx, 'latest', { 'tracer': 'callTracer', 'tracerConfig': { 'withLog': True}}], q))
    debug = await q.get()
    delay = time.monotonic()-ts
    h = tx['hash']
    if h not in known_txs:
        known_txs[h] = time.monotonic()
    else:
        delay = time.monotonic()-known_txs[h]
    stats['LOCAL'].append(delay)

async def feed_loop():
    global stats
    ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with websockets.connect(FEED_URL, extra_headers={'Authorization': GATEWAY_AUTH}, ssl=ssl_context, max_size=10*2**20) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1, 
            "method": 
            "subscribe", 
            "params": ["internalTxsMempool", {"include": [], "blockchain_network": "BSC-Mainnet"}]
        }))
        async for event in ws:
            data = json.loads(event)
            if 'params' in data:
                h = data['params']['result']['payload']['estimationTx']['hash']
                ts = time.monotonic()
                delay = 0
                if h in known_txs:
                    delay = ts-known_txs[h]
                else:
                    known_txs[h] = time.monotonic()
                stats['FEED'].append(delay)

async def gw_loop(call_queue):
    global stats
    async with websockets.connect(GATEWAY_URL, extra_headers={'Authorization': GATEWAY_AUTH}) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "subscribe",
            "params": ["newTxs", {"include": ["tx_contents"]}]
        }))
        async for event in ws:
            ts = time.monotonic()
            r = json.loads(event)
            if 'params' in r:
                h = r['params']['result']
                asyncio.create_task(trace_tx(h['txContents'], call_queue, ts))

async def stats_writer():
    global stats
    while True:
        await asyncio.sleep(5)
        try:
            print(f"avg. local delay={sum(stats['LOCAL'])/len(stats['LOCAL'])*1000:.03f}ms, local TXs={len(stats['LOCAL'])}, avg feed delay={sum(stats['FEED'])/len(stats['FEED'])*1000:.03f}ms, total feed TXs={len(stats['FEED'])}")
        except ZeroDivisionError:
            print("# Got zero TXs", len(stats['LOCAL']), len(stats['FEED']))
        stats = defaultdict(list)

async def main():
    call_queue = asyncio.Queue()
    await asyncio.gather(
        feed_loop(),
        gw_loop(call_queue),
        call_loop(call_queue),
        stats_writer(),
    )

if __name__ == '__main__':
    asyncio.run(main())